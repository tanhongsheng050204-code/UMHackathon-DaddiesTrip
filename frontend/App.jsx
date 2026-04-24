import React, { useState, useEffect, useRef } from 'react';
import { Plane, Calendar, Receipt, Send, ChevronRight, Mic, MicOff, AlertCircle, Loader2, X, AlertTriangle, ClipboardList } from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('plan');

  // Logic State
  const [prompt, setPrompt] = useState('');
  
  // Overlay & Error State
  const [overlayState, setOverlayState] = useState('hidden'); // 'hidden', 'loading', 'error'
  const [progressStatus, setProgressStatus] = useState('');
  const [progressPercent, setProgressPercent] = useState(0);
  const [errorMsg, setErrorMsg] = useState('');
  
  // Clarification State
  const [clarificationMsg, setClarificationMsg] = useState('');
  const [missingFields, setMissingFields] = useState([]);

  // Trip Data State
  const [tripData, setTripData] = useState(null);
  const [flightOptions, setFlightOptions] = useState([]);
  const [selectedFlightIdx, setSelectedFlightIdx] = useState(0);
  const [itinerary, setItinerary] = useState([]);
  const [splitData, setSplitData] = useState(null);
  const [numPax, setNumPax] = useState(1);

  // Voice State
  const [isRecording, setIsRecording] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState('');
  const recognitionRef = useRef(null);
  const interimBaseRef = useRef('');
  const wantToStopRef = useRef(false);

  // Settlement State
  const [showBudgetModal, setShowBudgetModal] = useState(false);
  const [cardNumber, setCardNumber] = useState('');
  const [cardHolder, setCardHolder] = useState('');
  const [cardExpiry, setCardExpiry] = useState('');
  const [cardCvv, setCardCvv] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [paymentSuccess, setPaymentSuccess] = useState(false);
  const [settleMessage, setSettleMessage] = useState('');

  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-MY';
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        setIsRecording(true);
        setVoiceStatus('🎙️ Listening... speak your trip request (click mic to stop)');
      };

      recognition.onresult = (event) => {
        let interimTranscript = '';
        let finalTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalTranscript += transcript;
          } else {
            interimTranscript += transcript;
          }
        }

        const separator = interimBaseRef.current && !interimBaseRef.current.endsWith(' ') && (interimTranscript || finalTranscript) ? ' ' : '';
        if (interimTranscript) {
          setPrompt(interimBaseRef.current + separator + interimTranscript);
          setVoiceStatus('🎙️ ' + interimTranscript);
        }
        if (finalTranscript) {
          const combined = interimBaseRef.current + separator + finalTranscript.trim();
          setPrompt(combined);
          interimBaseRef.current = combined;
          setVoiceStatus('🎙️ Listening... pause is OK, keep talking');
        }
      };

      recognition.onend = () => {
        if (!wantToStopRef.current && isRecording) {
          try {
            recognition.start();
            return;
          } catch (_) {}
        }
        setIsRecording(false);
        wantToStopRef.current = false;
        setVoiceStatus(prev => {
          if (prev.startsWith('⚠️')) return prev;
          if (prompt.trim() && interimBaseRef.current.trim()) return '✅ Done! You can edit the text or click mic again.';
          return '';
        });
        setTimeout(() => {
          setVoiceStatus(prev => prev.startsWith('✅') ? '' : prev);
        }, 3000);
      };

      recognition.onerror = (event) => {
        if (event.error === 'no-speech' && !wantToStopRef.current) return;
        setIsRecording(false);
        wantToStopRef.current = false;
        const msgs = {
          'not-allowed': '⚠️ Microphone access denied. Please allow it in browser settings.',
          'no-speech': '⚠️ No speech detected. Try speaking closer to the mic.',
          'network': '⚠️ Network error during voice recognition.',
          'aborted': ''
        };
        const msg = msgs[event.error] ?? `⚠️ Voice error: ${event.error}`;
        if (msg) {
          setVoiceStatus(msg);
          setTimeout(() => setVoiceStatus(''), 4000);
        }
      };

      recognitionRef.current = recognition;
    }
  }, [isRecording, prompt]);

  const handleVoiceToggle = () => {
    if (!recognitionRef.current) return;
    if (isRecording) {
      wantToStopRef.current = true;
      recognitionRef.current.stop();
    } else {
      wantToStopRef.current = false;
      interimBaseRef.current = prompt;
      try {
        recognitionRef.current.start();
      } catch (e) {
        setVoiceStatus('⚠️ Could not start microphone: ' + e.message);
      }
    }
  };

  const handleGenerate = async () => {
    if (!prompt) return;
    setOverlayState('loading');
    setErrorMsg('');
    setClarificationMsg('');
    setProgressStatus('Initializing orchestrator...');
    setProgressPercent(0);
    setFlightOptions([]);
    setItinerary([]);
    setSplitData(null);
    setTripData(null);

    let success = false;
    let isClarification = false;

    try {
      const response = await fetch('/api/plan-trip-stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt })
      });

      if (!response.ok) {
        let errDetail = `HTTP ${response.status}`;
        if (response.status === 504 || response.status === 502) {
            errDetail = 'The AI service is temporarily unavailable (gateway timeout). Please wait a moment and try again.';
        } else if (response.status === 429) {
            errDetail = 'Too many requests. Please wait a moment and try again.';
        } else if (response.status >= 500) {
            errDetail = `Server error (HTTP ${response.status}). Please try again later.`;
        } else {
            try { const errData = await response.json(); errDetail = errData.detail || errDetail; } catch (_) {}
        }
        throw new Error(errDetail);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        let lines = buffer.split('\n\n');
        buffer = lines.pop();

        for (let line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.substring(6);
            try {
              const event = JSON.parse(dataStr);
              if (event.type === 'progress') {
                setProgressStatus(event.text);
                setProgressPercent(p => Math.min(p + 15, 95));
              } else if (event.type === 'error') {
                throw new Error(event.message);
              } else if (event.type === 'clarification') {
                setClarificationMsg(event.message);
                setMissingFields(event.missing_fields || []);
                isClarification = true;
                break;
              } else if (event.type === 'partial_itinerary') {
                setItinerary(event.days || []);
                setNumPax(event.num_participants || 1);
              } else if (event.type === 'partial_flights') {
                setFlightOptions(event.flight_options || []);
                setNumPax(event.num_participants || 1);
              } else if (event.type === 'complete') {
                const data = event.data;
                const nPax = data.num_participants || data.participants?.length || 1;
                setNumPax(nPax);
                setFlightOptions(data.flight_options?.length ? data.flight_options : (data.flights ? [data.flights] : []));
                setItinerary(data.itinerary || []);
                setSplitData(data.split);
                setTripData(data);
                setProgressPercent(100);
                setProgressStatus('Done!');
                success = true;
              }
            } catch (e) {
              if (e.message !== "Unexpected end of JSON input" && !e.message.includes("JSON")) {
                throw e; // Rethrow actual errors thrown via throw new Error(event.message)
              }
            }
          }
        }
        if (isClarification) break;
      }
      
      if (!success && !isClarification) {
        throw new Error('Server stopped responding. Try a simpler prompt.');
      }
      
    } catch (error) {
      const msg = error.name === 'TypeError' && error.message.includes('Failed to fetch')
          ? 'Unable to connect to the server. Please check your internet connection and try again.'
          : error.message;
      setErrorMsg(msg);
      setOverlayState('error');
      return; // Early return to prevent hiding overlay
    } 

    if (success) {
      setTimeout(() => setOverlayState('hidden'), 500);
      setActiveTab('itinerary');
    } else if (isClarification) {
      setOverlayState('hidden');
    }
  };

  const getGrandTotal = () => {
    let hotelTotal = 0, foodTotal = 0, transTotal = 0, actTotal = 0;
    itinerary.forEach(day => {
        hotelTotal += (day.hotel ? (day.hotel.cost_myr || 0) : 0) * numPax;
        foodTotal += (day.daily_food_cost_myr || 0) * numPax;
        transTotal += (day.transportation ? (day.transportation.cost_myr || 0) : 0) * numPax;
        if (day.activities) day.activities.forEach(act => actTotal += (act.cost_myr || 0) * numPax);
    });
    const flightCostPerPax = flightOptions[selectedFlightIdx] ? (flightOptions[selectedFlightIdx].cost_myr || 0) : 0;
    const flightCostTotal = flightCostPerPax * numPax;
    return Math.round(flightCostTotal + hotelTotal + foodTotal + transTotal + actTotal);
  };

  const PILL_MAP = {
    destination:  { icon: '📍', label: 'Destination' },
    trip_dates:   { icon: '🗓️', label: 'Trip Dates' },
    participants: { icon: '👥', label: 'Participants' },
    budget:       { icon: '💰', label: 'Budget' },
  };

  const handleSettle = async () => {
    const rawCard = cardNumber.replace(/\s/g, '');
    if (rawCard.length < 16) {
      setSettleMessage('Please enter a valid 16-digit card number.');
      return;
    }
    setIsProcessing(true);
    setSettleMessage('Processing...');
    
    try {
      const response = await fetch('/api/settle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          group_id: "group_123", 
          user_id: "user_1", 
          card_number: rawCard 
        })
      });
      const data = await response.json();
      if (response.ok) {
        setPaymentSuccess(true);
        setTimeout(() => {
          setPaymentSuccess(false);
          setShowBudgetModal(false);
        }, 3000);
      } else {
        setSettleMessage(data.detail || 'Payment failed.');
      }
    } catch (error) {
      setSettleMessage('Connection failed.');
    } finally {
      setIsProcessing(false);
    }
  };

  const getExpensesBreakdown = () => {
    let hotel = 0, food = 0, trans = 0, act = 0;
    itinerary.forEach(day => {
      hotel += (day.hotel ? (day.hotel.cost_myr || 0) : 0) * numPax;
      food += (day.daily_food_cost_myr || 0) * numPax;
      trans += (day.transportation ? (day.transportation.cost_myr || 0) : 0) * numPax;
      if (day.activities) day.activities.forEach(a => act += (a.cost_myr || 0) * numPax);
    });
    const flight = (flightOptions[selectedFlightIdx]?.cost_myr || 0) * numPax;
    return { flight, hotel, food, trans, act, total: flight + hotel + food + trans + act };
  };

  return (
    <div className="min-h-screen bg-[#FDF9F3] text-gray-800 font-serif selection:bg-rose-200 relative overflow-hidden">
      
      {/* Full Page Overlay for Generation Progress & Errors */}
      {overlayState !== 'hidden' && (
        <div className="absolute inset-0 bg-white/80 backdrop-blur-sm z-50 flex items-center justify-center">
          <div className="bg-white p-8 rounded-3xl shadow-2xl max-w-md w-full text-center border border-gray-100 relative">
             {overlayState === 'error' ? (
               <>
                 <AlertTriangle className="text-red-500 mx-auto mb-4" size={48} />
                 <h3 className="text-2xl font-bold font-serif text-gray-800 mb-2">Something went wrong</h3>
                 <p className="text-red-600 font-sans mb-6">{errorMsg}</p>
                 <button 
                   onClick={() => setOverlayState('hidden')}
                   className="bg-gray-100 text-gray-700 px-6 py-2 rounded-full font-sans font-medium hover:bg-gray-200 transition-colors"
                 >
                   Close
                 </button>
               </>
             ) : (
               <>
                 <Loader2 className="animate-spin text-[#DE8170] mx-auto mb-4" size={48} />
                 <h3 className="text-2xl font-bold font-serif text-gray-800 mb-2">Orchestrating your trip...</h3>
                 <div className="w-full bg-gray-100 rounded-full h-2 mb-4 overflow-hidden">
                    <div className="bg-[#DE8170] h-2 rounded-full transition-all duration-300" style={{width: `${progressPercent}%`}}></div>
                 </div>
                 <p className="text-gray-500 font-sans">{progressStatus}</p>
               </>
             )}
          </div>
        </div>
      )}

      {/* HEADER SECTION */}
      <header className="flex flex-col items-center pt-16 pb-8">
        <div className="text-[#DE8170] mb-2">
          <Plane size={48} strokeWidth={1.5} />
        </div>
        <h1 className="text-6xl font-bold tracking-tight text-[#3A332C] mb-4">
          DaddiesTrip
        </h1>
        <p className="text-xl text-gray-500 font-sans tracking-wide">
          Your AI-powered travel orchestration companion
        </p>
      </header>

      {/* ERROR & CLARIFICATION BANNERS ON MAIN PAGE */}
      <div className="max-w-4xl mx-auto px-6 mb-4 font-sans">
        {errorMsg && overlayState === 'hidden' && (
          <div className="bg-red-50 border border-red-200 rounded-2xl p-4 flex items-start justify-between mb-4 shadow-sm">
            <div className="flex items-center">
              <AlertCircle className="text-red-500 mr-3 mt-0.5 flex-shrink-0" size={20} />
              <div className="text-red-700">{errorMsg}</div>
            </div>
            <button onClick={() => setErrorMsg('')} className="text-red-400 hover:text-red-600">
              <X size={20} />
            </button>
          </div>
        )}

        {clarificationMsg && (
          <div className="bg-amber-50 border border-amber-200 rounded-2xl p-5 mb-4 shadow-sm">
            <div className="flex justify-between items-start mb-3">
              <div className="flex items-center text-amber-800 font-bold">
                <ClipboardList className="mr-2" size={20} />
                📋 Missing Information
              </div>
              <button onClick={() => setClarificationMsg('')} className="text-amber-500 hover:text-amber-700">
                <X size={20} />
              </button>
            </div>
            {missingFields.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-3">
                {missingFields.map(f => {
                  const p = PILL_MAP[f] || { icon: '❓', label: f };
                  return (
                    <span key={f} className="bg-white border border-amber-200 text-amber-800 px-3 py-1 rounded-full text-sm font-medium flex items-center shadow-sm">
                      <span className="mr-1">{p.icon}</span> {p.label}
                    </span>
                  );
                })}
              </div>
            )}
            <p className="text-amber-700 text-sm">{clarificationMsg}</p>
          </div>
        )}
      </div>

      {/* NAVIGATION TABS */}
      <div className="flex justify-center mb-12">
        <div className="bg-white rounded-full p-2 shadow-sm flex space-x-2 border border-gray-100">
          <button
            onClick={() => setActiveTab('plan')}
            className={`flex items-center px-8 py-3 rounded-full transition-all font-sans font-medium ${activeTab === 'plan'
                ? 'bg-[#DE8170] text-white shadow-md'
                : 'text-gray-600 hover:bg-gray-50'
              }`}
          >
            <Plane className="mr-2" size={18} />
            Plan Trip
          </button>
          <button
            onClick={() => setActiveTab('itinerary')}
            className={`flex items-center px-8 py-3 rounded-full transition-all font-sans font-medium ${activeTab === 'itinerary'
                ? 'bg-[#DE8170] text-white shadow-md'
                : 'text-gray-600 hover:bg-gray-50'
              }`}
          >
            <Calendar className="mr-2" size={18} />
            Itinerary
          </button>
          <button
            onClick={() => setActiveTab('expenses')}
            className={`flex items-center px-8 py-3 rounded-full transition-all font-sans font-medium ${activeTab === 'expenses'
                ? 'bg-[#DE8170] text-white shadow-md'
                : 'text-gray-600 hover:bg-gray-50'
              }`}
          >
            <Receipt className="mr-2" size={18} />
            Expenses
          </button>
        </div>
      </div>

      {/* MAIN CONTENT AREA */}
      <main className="max-w-4xl mx-auto px-6 pb-24">
        <div className="bg-white rounded-[2rem] shadow-sm border border-gray-100 p-8 min-h-[400px]">

          {/* PLAN TRIP TAB */}
          {activeTab === 'plan' && (
            <div className="flex flex-col h-full font-sans">
              <div className="flex items-start mb-6">
                <div className="bg-[#DE8170] text-white p-3 rounded-full mr-4 shadow-sm flex-shrink-0">
                  <Plane size={24} />
                </div>
                <div className="bg-[#FAF6F0] rounded-2xl rounded-tl-none p-6 text-gray-700 text-lg leading-relaxed shadow-sm border border-gray-100 max-w-2xl">
                  Hello! I'm your AI travel companion. Tell me about your dream trip – where would you like to go, who's traveling with you, when, and what's your budget?
                </div>
              </div>

              {/* Input Area */}
              <div className="mt-auto pt-8">
                {voiceStatus && (
                  <div className={`mb-2 text-sm font-medium ${voiceStatus.includes('⚠️') ? 'text-red-500' : 'text-blue-500'}`}>
                    {voiceStatus}
                  </div>
                )}
                <div className="relative flex items-center">
                  <input
                    type="text"
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
                    placeholder="e.g. 5 days in Bali for 4 people under RM2000..."
                    className="w-full bg-gray-50 border border-gray-200 rounded-full px-6 py-4 pr-24 text-gray-700 focus:outline-none focus:ring-2 focus:ring-[#DE8170]/50 transition-all shadow-inner"
                  />
                  <div className="absolute right-2 flex space-x-1">
                    <button 
                      onClick={handleVoiceToggle}
                      className={`p-2 rounded-full transition-colors flex items-center justify-center w-10 ${isRecording ? 'bg-red-100 text-red-600 animate-pulse' : 'bg-gray-200 text-gray-600 hover:bg-gray-300'}`}
                      title="Voice Input"
                    >
                      {isRecording ? <MicOff size={18} /> : <Mic size={18} />}
                    </button>
                    <button 
                      onClick={handleGenerate}
                      disabled={overlayState === 'loading' || !prompt}
                      className="bg-[#DE8170] text-white p-2 rounded-full hover:bg-[#d4705f] disabled:opacity-50 transition-colors flex items-center justify-center w-10"
                    >
                      <Send size={18} className="ml-1" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ITINERARY TAB */}
          {activeTab === 'itinerary' && (
            <div className="font-sans">
              {!tripData && !itinerary.length ? (
                <div className="text-center py-20 text-gray-400">
                  <Calendar size={48} className="mx-auto mb-4 opacity-50" />
                  <p>Your itinerary will appear here once generated.</p>
                </div>
              ) : (
                <>
                  <div className="bg-[#DE8170] text-white rounded-2xl p-8 mb-8 shadow-md">
                    <h2 className="text-4xl font-serif font-bold mb-2">{itinerary[0]?.location || 'Destination'}</h2>
                    <div className="flex items-center opacity-90">
                      <Calendar size={16} className="mr-2" />
                      <span>{itinerary.length} Days • {numPax} travelers</span>
                    </div>
                  </div>

                  {flightOptions.length > 0 && (
                    <>
                      <h3 className="text-xl font-bold text-gray-800 mb-4 px-2">Flight Options</h3>
                      <div className="grid grid-cols-2 gap-6 mb-10">
                        {flightOptions.map((opt, i) => {
                           const dep = opt.departure || {};
                           const ret = opt.return || {};
                           const airline = opt.airline || `Option ${i + 1}`;
                           const costPerPax = opt.cost_myr || 0;
                           const isSelected = selectedFlightIdx === i;

                           // Build date-specific Skyscanner link
                           let skyscannerHref = opt.source || '#';
                           if (skyscannerHref === '#' || !skyscannerHref.includes('/kul/')) {
                             const destIATA = (ret.airport || '').toLowerCase() || 'sin';
                             const depD = (dep.date || '').replace(/-/g, '');
                             const retD = (ret.date || '').replace(/-/g, '');
                             if (depD.length >= 8 && retD.length >= 8) {
                               skyscannerHref = `https://www.skyscanner.com.my/transport/flights/kul/${destIATA}/${depD.slice(2)}/${retD.slice(2)}/`;
                             }
                           }

                           // Build Google Flights link
                           let googleFlightsHref = opt.google_flights || '#';
                           if (googleFlightsHref === '#' || !googleFlightsHref.includes('on+')) {
                             const destIATA = ret.airport || 'SIN';
                             const airlineName = (opt.airline || '').replace(/\s+/g, '+');
                             const depDateStr = dep.date || '';
                             if (depDateStr) {
                               googleFlightsHref = `https://www.google.com/travel/flights?q=Flights+from+KUL+to+${destIATA}+on+${depDateStr}${airlineName ? '+with+' + airlineName : ''}&curr=MYR&hl=en&gl=MY`;
                             }
                           }

                           return (
                             <div key={i} onClick={() => setSelectedFlightIdx(i)} className={`border rounded-2xl p-6 transition-colors cursor-pointer group ${isSelected ? 'border-[#DE8170] bg-white shadow-md' : 'border-gray-200 bg-gray-50 hover:border-[#DE8170] hover:bg-white'}`}>
                               <div className="flex justify-between items-center mb-4">
                                 <span className="font-semibold text-gray-700">{airline}</span>
                                 <span className={`text-xs font-bold px-3 py-1 rounded-full ${isSelected ? 'bg-[#DE8170]/10 text-[#DE8170]' : 'bg-gray-200 text-gray-700'}`}>RM {costPerPax}</span>
                               </div>
                               <div className="flex justify-between items-center text-sm text-gray-500 mb-4">
                                 <div className="text-center">
                                   <div className="text-2xl font-bold text-gray-800 mb-1">{dep.airport || 'KUL'}</div>
                                   {dep.time || 'TBD'}
                                 </div>
                                 <div className="flex-1 border-t-2 border-dashed border-gray-300 mx-4 relative">
                                   <Plane size={16} className={`absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 transition-colors ${isSelected ? 'text-[#DE8170]' : 'text-gray-400 group-hover:text-[#DE8170]'}`} />
                                 </div>
                                 <div className="text-center">
                                   <div className="text-2xl font-bold text-gray-800 mb-1">{ret.airport || 'DPS'}</div>
                                   {ret.arrival_time || 'TBD'}
                                 </div>
                               </div>
                               <div className="flex gap-2 mt-4">
                                 <a href={skyscannerHref} target="_blank" rel="noopener" className="text-xs font-medium text-[#DE8170] hover:underline" onClick={(e) => e.stopPropagation()}>Skyscanner ↗</a>
                                 <a href={googleFlightsHref} target="_blank" rel="noopener" className="text-xs font-medium text-[#DE8170] hover:underline" onClick={(e) => e.stopPropagation()}>Google Flights ↗</a>
                               </div>
                             </div>
                           );
                        })}
                      </div>
                    </>
                  )}

                  <h3 className="text-xl font-bold text-gray-800 mb-4 px-2">Daily Itinerary</h3>
                  {itinerary.map((day, dayIdx) => {
                    const dayNum = day.day || (dayIdx + 1);
                    const dayLocation = day.location || 'Destination';
                    const dayActivities = Array.isArray(day.activities) ? day.activities : [];

                    return (
                      <div key={dayIdx} className="relative pl-8 border-l-2 border-[#DE8170]/30 pb-8 ml-4">
                        <div className="absolute w-8 h-8 bg-[#DE8170] rounded-full text-white flex items-center justify-center font-bold text-sm -left-[17px] top-0 shadow-md">
                          {dayNum}
                        </div>
                        <h4 className="text-lg font-bold text-gray-800 mb-6 ml-4">{dayLocation}</h4>

                        <div className="ml-4 space-y-6">
                          {dayActivities.length > 0 ? dayActivities.map((act, actIdx) => {
                            const embedMap = `https://maps.google.com/maps?q=${encodeURIComponent((act.name || 'location') + ' ' + dayLocation)}&t=&z=14&ie=UTF8&iwloc=&output=embed`;
                            return (
                              <div key={actIdx} className="bg-gray-50 rounded-xl p-5 border border-gray-100 hover:shadow-md transition-shadow relative">
                                <span className="absolute top-5 right-5 text-xs font-bold bg-gray-200 text-gray-700 px-2 py-1 rounded">RM {act.cost_myr || 0}</span>
                                <h5 className="font-bold text-gray-800 mb-2">{act.name}</h5>
                                <p className="text-sm text-gray-500 mb-2">{act.schedule || 'Flexible'} • {dayLocation}</p>
                                {act.rating && (
                                  <div className="text-xs font-medium text-yellow-600 bg-yellow-50 inline-block px-2 py-1 rounded mb-2">
                                    ★ {act.rating}
                                  </div>
                                )}
                                <div className="rounded-lg overflow-hidden border border-gray-200 h-24 w-full max-w-sm">
                                  <iframe src={embedMap} width="100%" height="100%" style={{ border: 0 }} allowFullScreen="" loading="lazy"></iframe>
                                </div>
                              </div>
                            );
                          }) : (
                            <p className="text-gray-400 italic">No specific activities planned.</p>
                          )}
                        </div>
                        
                        <div className="ml-4 mt-6 flex gap-4">
                          <div className="flex-1 bg-gray-50 rounded-xl p-4 border border-gray-100">
                             <h5 className="font-bold text-gray-800 text-sm mb-1">🏨 Stay</h5>
                             <p className="text-sm text-gray-600">{day.hotel?.name || 'Hotel in ' + dayLocation}</p>
                             <p className="text-xs font-semibold mt-1">RM {day.hotel?.cost_myr || 0}/night</p>
                          </div>
                          <div className="flex-1 bg-gray-50 rounded-xl p-4 border border-gray-100">
                             <h5 className="font-bold text-gray-800 text-sm mb-1">🍽️ Eat</h5>
                             <p className="text-sm text-gray-600">~ RM {day.daily_food_cost_myr || 0}/pax</p>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </>
              )}
            </div>
          )}

          {/* EXPENSES TAB */}
          {activeTab === 'expenses' && (
            <div className="font-sans">
              {!tripData && !splitData ? (
                <div className="text-center py-20 text-gray-400">
                  <Receipt size={48} className="mx-auto mb-4 opacity-50" />
                  <p>Trip expenses will be detailed here.</p>
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-3 gap-6 mb-10">
                    <div className="bg-[#DE8170] text-white p-6 rounded-2xl shadow-md">
                      <p className="text-white/80 font-medium mb-1 text-sm flex items-center"><Receipt size={14} className="mr-2" /> Total Expenses</p>
                      <h3 className="text-3xl font-serif font-bold">RM {getGrandTotal().toLocaleString()}</h3>
                    </div>
                    <div className="bg-[#8E9F7F] text-white p-6 rounded-2xl shadow-md">
                      <p className="text-white/80 font-medium mb-1 text-sm flex items-center"><Calendar size={14} className="mr-2" /> Per Person</p>
                      <h3 className="text-3xl font-serif font-bold">RM {splitData?.split_per_person_myr || Math.round(getGrandTotal() / numPax)}</h3>
                    </div>
                    <div className="bg-[#7D6B5A] text-white p-6 rounded-2xl shadow-md">
                      <p className="text-white/80 font-medium mb-1 text-sm flex items-center"><Plane size={14} className="mr-2" /> Local ({splitData?.destination_currency || 'MYR'})</p>
                      <h3 className="text-3xl font-serif font-bold">{splitData?.split_per_person_local || 0}</h3>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-12">
                    {/* Expenses List */}
                    <div>
                      <div className="flex justify-between items-center mb-6">
                        <h3 className="text-xl font-bold text-gray-800">Expenses Breakdown</h3>
                      </div>

                      <div className="space-y-6">
                        {itinerary.map((day, idx) => {
                          const hotelCost = (day.hotel?.cost_myr || 0) * numPax;
                          if (hotelCost > 0 && (!idx || day.hotel?.name !== itinerary[idx-1]?.hotel?.name)) {
                            return (
                              <div key={`h-${idx}`} className="flex justify-between items-start border-b border-gray-100 pb-4">
                                <div>
                                  <h4 className="font-bold text-gray-800">Hotel - {day.hotel?.name || 'Accommodation'}</h4>
                                  <p className="text-xs text-gray-500 mt-1">Accommodation</p>
                                </div>
                                <div className="text-right">
                                  <div className="font-bold text-gray-800">RM {hotelCost}</div>
                                  <div className="text-xs text-gray-400">RM {day.hotel.cost_myr} each</div>
                                </div>
                              </div>
                            );
                          }
                          return null;
                        })}

                        {flightOptions[selectedFlightIdx] && (
                           <div className="flex justify-between items-start border-b border-gray-100 pb-4">
                             <div>
                               <h4 className="font-bold text-gray-800">Flight Tickets ({flightOptions[selectedFlightIdx].airline})</h4>
                               <p className="text-xs text-gray-500 mt-1">Transportation</p>
                             </div>
                             <div className="text-right">
                               <div className="font-bold text-gray-800">RM {flightOptions[selectedFlightIdx].cost_myr * numPax}</div>
                               <div className="text-xs text-gray-400">RM {flightOptions[selectedFlightIdx].cost_myr} each</div>
                             </div>
                           </div>
                        )}
                        
                        <div className="flex justify-between items-start border-b border-gray-100 pb-4">
                           <div>
                             <h4 className="font-bold text-gray-800">Food & Dining</h4>
                             <p className="text-xs text-gray-500 mt-1">Estimated total</p>
                           </div>
                           <div className="text-right">
                             <div className="font-bold text-gray-800">RM {itinerary.reduce((acc, d) => acc + (d.daily_food_cost_myr || 0), 0) * numPax}</div>
                             <div className="text-xs text-gray-400">RM {itinerary.reduce((acc, d) => acc + (d.daily_food_cost_myr || 0), 0)} each</div>
                           </div>
                        </div>

                      </div>
                    </div>

                    <div>
                      <h3 className="text-xl font-bold text-gray-800 mb-6">Settlement</h3>
                      <button 
                        onClick={() => setShowBudgetModal(true)}
                        className="w-full bg-[#DE8170] text-white py-4 rounded-2xl font-bold shadow-lg hover:bg-[#d4705f] transition-all flex items-center justify-center gap-2"
                      >
                        <Receipt size={20} />
                        Review & Settle Balance
                      </button>
                      <p className="text-xs text-gray-400 mt-3 text-center">Secure checkout powered by DaddiesTrip Ledger</p>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

        </div>
      </main>

      {/* Settlement Modal */}
      {showBudgetModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[60] flex items-center justify-center p-6">
          <div className="bg-white rounded-[2.5rem] shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto p-10 relative">
            <button onClick={() => setShowBudgetModal(false)} className="absolute top-6 right-6 text-gray-400 hover:text-gray-600">
              <X size={24} />
            </button>
            
            <div className="grid grid-cols-2 gap-12">
              {/* Breakdown Table */}
              <div>
                <h2 className="text-3xl font-serif font-bold text-gray-800 mb-6">Budget Breakdown</h2>
                <div className="space-y-4 font-sans">
                  {Object.entries(getExpensesBreakdown()).map(([key, val]) => {
                    if (key === 'total') return null;
                    const labels = { flight: '✈️ Flights', hotel: '🏨 Accommodation', food: '🍜 Food & Dining', trans: '🚇 Transportation', act: '🎟️ Activities' };
                    return (
                      <div key={key} className="flex justify-between py-2 border-b border-gray-100">
                        <span className="text-gray-600">{labels[key]}</span>
                        <span className="font-bold">RM {val.toLocaleString()}</span>
                      </div>
                    );
                  })}
                  <div className="flex justify-between py-4 bg-gray-50 px-4 rounded-xl mt-4">
                    <span className="font-bold text-gray-800">Total (All Travelers)</span>
                    <span className="font-bold text-[#DE8170] text-xl">RM {getExpensesBreakdown().total.toLocaleString()}</span>
                  </div>
                </div>
              </div>

              {/* Payment UI */}
              <div className="font-sans">
                <h3 className="text-xl font-bold text-gray-800 mb-6">Secure Payment</h3>
                
                {/* Visual Card */}
                <div className="bg-gradient-to-br from-gray-800 to-gray-900 rounded-2xl p-6 text-white shadow-xl mb-8 relative overflow-hidden h-48 flex flex-col justify-between">
                  <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 rounded-full -mr-16 -mt-16"></div>
                  <div className="w-12 h-10 bg-amber-400/20 rounded-md border border-amber-400/30"></div>
                  <div className="text-2xl tracking-[0.25em] font-mono">
                    {cardNumber || '•••• •••• •••• ••••'}
                  </div>
                  <div className="flex justify-between items-end uppercase text-[10px] tracking-widest">
                    <div>
                      <div className="opacity-50 mb-1">Card Holder</div>
                      <div className="text-sm tracking-normal">{cardHolder || 'YOUR NAME'}</div>
                    </div>
                    <div>
                      <div className="opacity-50 mb-1">Expires</div>
                      <div className="text-sm tracking-normal">{cardExpiry || 'MM/YY'}</div>
                    </div>
                  </div>
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1 block">Card Number</label>
                    <input 
                      type="text" 
                      placeholder="1234 5678 9012 3456"
                      value={cardNumber}
                      onChange={(e) => {
                        let val = e.target.value.replace(/\D/g, '').substring(0, 16);
                        let formatted = val.match(/.{1,4}/g)?.join(' ') || val;
                        setCardNumber(formatted);
                      }}
                      className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-[#DE8170]/30"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1 block">Cardholder Name</label>
                    <input 
                      type="text" 
                      placeholder="John Doe"
                      value={cardHolder}
                      onChange={(e) => setCardHolder(e.target.value.toUpperCase())}
                      className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-[#DE8170]/30"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1 block">Expiry</label>
                      <input 
                        type="text" 
                        placeholder="MM/YY"
                        value={cardExpiry}
                        onChange={(e) => {
                          let val = e.target.value.replace(/\D/g, '').substring(0, 4);
                          if (val.length >= 3) val = val.substring(0, 2) + '/' + val.substring(2);
                          setCardExpiry(val);
                        }}
                        className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-[#DE8170]/30"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1 block">CVV</label>
                      <input 
                        type="password" 
                        placeholder="•••"
                        maxLength="3"
                        value={cardCvv}
                        onChange={(e) => setCardCvv(e.target.value.replace(/\D/g, ''))}
                        className="w-full bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-[#DE8170]/30"
                      />
                    </div>
                  </div>
                </div>

                <button 
                  onClick={handleSettle}
                  disabled={isProcessing}
                  className="w-full bg-[#DE8170] text-white py-4 rounded-xl font-bold mt-8 shadow-lg hover:bg-[#d4705f] disabled:opacity-50 transition-all"
                >
                  {isProcessing ? 'Processing...' : 'Pay Now'}
                </button>
                {settleMessage && <p className={`mt-2 text-center text-sm font-medium ${settleMessage.includes('Success') ? 'text-green-600' : 'text-red-500'}`}>{settleMessage}</p>}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Success Animation Overlay */}
      {paymentSuccess && (
        <div className="fixed inset-0 bg-white/95 z-[70] flex flex-col items-center justify-center animate-in fade-in duration-500">
          <div className="w-24 h-24 rounded-full border-4 border-green-500 flex items-center justify-center mb-6">
            <svg className="w-12 h-12 text-green-500 animate-in zoom-in duration-500 delay-200 fill-none stroke-current stroke-[4]" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h3 className="text-3xl font-serif font-bold text-gray-800">Payment Successful</h3>
          <p className="text-gray-500 font-sans mt-2">Your trip has been booked!</p>
        </div>
      )}
    </div>
  );
}
