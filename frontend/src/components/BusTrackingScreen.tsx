
import React, { useCallback, useState } from 'react';
import { BusTrip } from '../types/transit';
import { LiveTrackingMap, TrackingUpdate } from './LiveTrackingMap';
import {
  ArrowLeft,
  CheckCircle2,
  Navigation,
  CloudSun
} from 'lucide-react';

interface BusTrackingScreenProps {
  trip: BusTrip;
  onBackToBuses: () => void;
  selectedDateText?: string;
  selectedDate?: string;
}

export const BusTrackingScreen: React.FC<BusTrackingScreenProps> = ({
  trip,
  onBackToBuses,
  selectedDateText = 'Today',
  selectedDate
}) => {
  const [selectedStopId, setSelectedStopId] = useState<string | null>(null);
  const [tracking, setTracking] = useState<TrackingUpdate>({
    progress: 0,
    clockTime: 'Syncing time…',
    currentStopIndex: 0,
    status: 'NOT STARTED',
    actualTimes: {}
  });

  const handleTrackingUpdate = useCallback((update: TrackingUpdate) => {
    setTracking(update);
  }, []);

  return (
    <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-5 space-y-4">
      <div>
        <button
          onClick={onBackToBuses}
          className="inline-flex items-center gap-2 text-sm font-medium text-slate-400 hover:text-white transition-colors group"
        >
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
          <span>Back to buses</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
        <div className="lg:col-span-5 bg-[#0a1120] border border-slate-800 rounded-3xl p-6 shadow-2xl flex flex-col justify-between space-y-6">
          <div className="space-y-5">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-slate-400 font-semibold tracking-wider">
                {trip.routeCode}
              </span>
              <span className="px-3 py-1 rounded-full bg-blue-600/20 border border-blue-500/40 text-[11px] font-bold font-mono text-blue-300 tracking-wide">
                {trip.serviceClass}
              </span>
            </div>

            <div>
              <h1 className="text-3xl sm:text-4xl font-black text-white font-mono tracking-tight">
                {trip.id}
              </h1>
              <div className="text-base text-slate-300 font-medium mt-1">
                {trip.origin} <span className="text-cyan-400">→</span> {trip.destination}
              </div>
              <div className="flex items-center gap-2 mt-2">
                <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold tracking-wider border ${
                  tracking.status === 'RUNNING'
                    ? 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30'
                    : tracking.status === 'COMPLETED'
                      ? 'text-cyan-300 bg-cyan-500/10 border-cyan-500/30'
                      : 'text-amber-300 bg-amber-500/10 border-amber-500/30'
                }`}>
                  {tracking.status}
                </span>
                <span className="text-[11px] font-mono text-slate-400">{tracking.clockTime}</span>
              </div>
              <div className="text-xs text-slate-400 mt-1">
                {tracking.status === 'NOT STARTED'
                  ? `Scheduled to depart at ${trip.departureTime}`
                  : tracking.status === 'COMPLETED'
                    ? `Arrived at ${trip.destination}`
                    : `Heading to ${trip.stops[tracking.currentStopIndex]?.name || trip.destination}`}
              </div>
            </div>

            {/* Trip metrics */}
            <div className="grid grid-cols-3 gap-2.5 p-3 rounded-2xl bg-[#080d18] border border-slate-800/80">
              <div className="p-2 space-y-0.5">
                <div className="text-[10px] uppercase font-mono text-slate-500 font-semibold">DEPARTURE</div>
                <div className="text-base font-bold font-mono text-white">{trip.departureTime}</div>
              </div>

              <div className="p-2 space-y-0.5">
                <div className="text-[10px] uppercase font-mono text-slate-500 font-semibold">ARRIVAL</div>
                <div className="text-base font-bold font-mono text-cyan-400">{trip.predictedArrival}</div>
                <div className="text-[10px] font-mono text-slate-500">sch {trip.scheduledArrival}</div>
              </div>

              <div className="p-2 space-y-0.5">
                <div className="text-[10px] uppercase font-mono text-slate-500 font-semibold">DURATION</div>
                <div className="text-base font-bold font-mono text-white">{trip.duration}</div>
              </div>

              <div className="p-2 space-y-0.5 border-t border-slate-800/80 pt-2">
                <div className="text-[10px] uppercase font-mono text-slate-500 font-semibold">DISTANCE</div>
                <div className="text-base font-bold font-mono text-white">{trip.distanceKm} km</div>
                <div className="text-[10px] font-mono text-slate-500">{trip.stops.length} stops</div>
              </div>

              <div className="p-2 space-y-0.5 border-t border-slate-800/80 pt-2">
                <div className="text-[10px] uppercase font-mono text-slate-500 font-semibold">DELAY / TRAFFIC</div>
                <div className="text-base font-bold font-mono text-cyan-400">
                  {trip.delayMinutes > 0 ? `+${trip.delayMinutes} min` : 'On Time'}
                </div>
                <div className="text-[10px] font-mono text-slate-400 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  <span>{trip.trafficStatus}</span>
                </div>
              </div>

              <div className="p-2 space-y-0.5 border-t border-slate-800/80 pt-2">
                <div className="text-[10px] uppercase font-mono text-slate-500 font-semibold">WEATHER</div>
                <div className="text-base font-bold font-mono text-white">{trip.weatherStatus}</div>
                <div className="text-[10px] font-mono text-slate-500">{selectedDateText}</div>
              </div>
            </div>

            {/* Stops timeline */}
            <div className="space-y-3 pt-2">
              <div className="flex items-center gap-2 text-xs font-bold text-cyan-400 uppercase tracking-wider">
                <Navigation className="w-4 h-4 text-cyan-400 rotate-45" />
                <span>Stops on this trip</span>
              </div>

              <p className="text-[10px] text-slate-500">Scheduled and predicted times are from the trip data. Simulated actual times are generated by the playback, not live GPS.</p>
              <div className="space-y-3 pl-1">
                {trip.stops.map((stop, index) => {
                  const isPassed = tracking.status === 'COMPLETED'
                    ? index < trip.stops.length - 1
                    : index < tracking.currentStopIndex;
                  const isCurrent = tracking.status === 'NOT STARTED'
                    ? index === 0
                    : tracking.status === 'COMPLETED'
                      ? index === trip.stops.length - 1
                      : index === tracking.currentStopIndex;
                  const isSelected = selectedStopId === stop.id;

                  return (
                    <div
                      key={stop.id}
                      onClick={() => setSelectedStopId(stop.id)}
                      className={`flex items-center justify-between p-2 rounded-xl transition-colors cursor-pointer ${
                        isSelected ? 'bg-slate-800/60' : 'hover:bg-slate-900/60'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        {isPassed ? (
                          <div className="w-6 h-6 rounded-full bg-slate-800 flex items-center justify-center">
                            <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                          </div>
                        ) : isCurrent ? (
                          <div className="w-6 h-6 rounded-full bg-amber-500/20 border border-amber-400 flex items-center justify-center">
                            <div className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse" />
                          </div>
                        ) : (
                          <div className="w-6 h-6 rounded-full bg-slate-900 border border-slate-700 flex items-center justify-center text-[10px] font-mono text-slate-500">
                            {index + 1}
                          </div>
                        )}

                        <div>
                          <div
                            className={`text-sm font-semibold ${
                              isCurrent
                                ? 'text-amber-300 font-bold'
                                : isPassed
                                  ? 'text-slate-300'
                                  : 'text-slate-400'
                            }`}
                          >
                            {stop.name}
                          </div>

                          {index === 0 && (
                            <div className="text-[10px] font-mono font-bold text-cyan-400 uppercase tracking-wider">
                              JOURNEY START
                            </div>
                          )}

                          {isCurrent && (
                            <div className="text-[10px] font-mono font-bold text-amber-400 uppercase tracking-wider">
                              CURRENT STOP
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="text-right font-mono">
                        <div className="text-[10px] text-slate-500">
                          Scheduled {stop.scheduledTime}
                        </div>
                        <div
                          className={`text-xs font-semibold ${
                            tracking.actualTimes[stop.id]
                              ? 'text-emerald-400'
                              : isCurrent
                                ? 'text-amber-300'
                                : isPassed
                                  ? 'text-slate-300'
                                  : 'text-slate-400'
                          }`}
                        >
                          {tracking.actualTimes[stop.id]
                            ? `Reached ${tracking.actualTimes[stop.id]}`
                            : `Predicted ${stop.predictedTime}`}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400 font-mono">
            <span className="flex items-center gap-1.5 text-slate-300">
              <CloudSun className="w-4 h-4 text-cyan-400" />
              <span>{trip.weatherStatus}</span>
            </span>
            <span className="text-cyan-400 font-semibold">
              {trip.stops.length} route stops
            </span>
          </div>
        </div>

        <div className="lg:col-span-7 flex flex-col h-full min-h-[580px]">
          <LiveTrackingMap
            trip={trip}
            selectedDate={selectedDate}
            onStopSelect={stopId => setSelectedStopId(stopId)}
            onTrackingUpdate={handleTrackingUpdate}
          />
        </div>
      </div>
    </div>
  );
};
