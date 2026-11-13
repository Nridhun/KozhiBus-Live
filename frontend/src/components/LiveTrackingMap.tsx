import React, { useState, useEffect, useRef, useMemo } from 'react';
import { BusTrip } from '../types/transit';
import { BusMarker } from './BusMarker';
import { Maximize2, Minimize2, Compass, ZoomIn, ZoomOut, RotateCcw } from 'lucide-react';

export interface TrackingUpdate {
  progress: number;
  clockTime: string;
  currentStopIndex: number;
  status: 'NOT STARTED' | 'RUNNING' | 'COMPLETED';
  actualTimes: Record<string, string>;
}

interface LiveTrackingMapProps {
  trip: BusTrip;
  selectedDate?: string;
  onStopSelect?: (stopId: string) => void;
  onTrackingUpdate?: (update: TrackingUpdate) => void;
}

// Route coordinates used by the SVG map.
interface Point {
  x: number;
  y: number;
}

interface AnimationState {
  segmentIndex: number;
  segmentElapsedSeconds: number;
  dwellRemainingSeconds: number;
  elapsedJourneySeconds: number;
}

const STOP_DWELL_SECONDS = 4;

const clockToMinutes = (value: string): number => {
  const [hours, minutes] = value.split(':').map(Number);
  return Number.isFinite(hours) && Number.isFinite(minutes)
    ? hours * 60 + minutes
    : 0;
};

const formatJourneyClock = (departureTime: string, elapsedSeconds: number): string => {
  const startSeconds = clockToMinutes(departureTime) * 60;
  const totalSeconds = startSeconds + Math.floor(elapsedSeconds);
  const hours = Math.floor(totalSeconds / 3600) % 24;
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const pad = (value: number) => value.toString().padStart(2, '0');
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)} IST`;
};

const getKolkataTimeSeconds = (): number => {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Kolkata',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23'
  }).formatToParts(new Date());
  const part = (type: string) => Number(parts.find(item => item.type === type)?.value ?? 0);
  return part('hour') * 3600 + part('minute') * 60 + part('second');
};

const getKolkataDateString = (): string => {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Kolkata',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).formatToParts(new Date());
  const part = (type: string) => parts.find(item => item.type === type)?.value ?? '';
  return `${part('year')}-${part('month')}-${part('day')}`;
};

const formatClockSeconds = (totalSeconds: number): string => {
  const safeSeconds = ((Math.floor(totalSeconds) % 86400) + 86400) % 86400;
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  const seconds = safeSeconds % 60;
  const pad = (value: number) => value.toString().padStart(2, '0');
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)} IST`;
};

export const LiveTrackingMap: React.FC<LiveTrackingMapProps> = ({ trip, selectedDate, onStopSelect, onTrackingUpdate }) => {
  // Bus position and status are synchronized automatically to the Asia/Kolkata clock.
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const isManualMode = false;
  // 1x = one timetable second per real second; 5x = five timetable seconds per real second.
  const [speedMultiplier, setSpeedMultiplier] = useState<number>(1);
  const [progress, setProgress] = useState<number>(0);
  const [currentStopIndex, setCurrentStopIndex] = useState<number>(0);
  const [isAtStop, setIsAtStop] = useState<boolean>(false);
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [panOffset, setPanOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const animationStateRef = useRef<AnimationState>({
    segmentIndex: 0,
    segmentElapsedSeconds: 0,
    dwellRemainingSeconds: 0,
    elapsedJourneySeconds: 0
  });

  const [clockTime, setClockTime] = useState<string>(
    formatJourneyClock(trip.departureTime, 0)
  );

  // Build the route coordinates from the trip's stops.
  const routePoints: Point[] = useMemo(
    () => trip.stops.map(stop => ({ x: stop.x, y: stop.y })),
    [trip.stops]
  );

  // Geometric segment lengths are used only to place the bus on the drawn route.
  const segmentLengths = useMemo(() => {
    const lengths: number[] = [];
    let total = 0;
    for (let i = 0; i < routePoints.length - 1; i++) {
      const first = routePoints[i];
      const second = routePoints[i + 1];
      const length = Math.hypot(second.x - first.x, second.y - first.y);
      lengths.push(length);
      total += length;
    }
    return { lengths, total };
  }, [routePoints]);

  // Each travel segment follows the time difference between consecutive predicted stop times.
  // The 4-second animation dwell is deliberately NOT added to timetable data.
  const segmentDurations = useMemo(() => {
    return trip.stops.slice(0, -1).map((stop, index) => {
      const nextStop = trip.stops[index + 1];
      const segmentStartTime = index === 0 ? trip.departureTime : stop.predictedTime;
      let minutes = clockToMinutes(nextStop.predictedTime) - clockToMinutes(segmentStartTime);

      // Handle a journey that crosses midnight.
      if (minutes < 0) minutes += 24 * 60;

      // Fallback for missing/equal stop times: use the distance difference if available.
      if (!Number.isFinite(minutes) || minutes <= 0) {
        const distanceDifference =
          typeof stop.distanceKm === 'number' && typeof nextStop.distanceKm === 'number'
            ? Math.max(0, nextStop.distanceKm - stop.distanceKm)
            : 0;
        minutes = distanceDifference > 0 ? distanceDifference * 2 : 1;
      }

      return minutes * 60;
    });
  }, [trip.stops, trip.departureTime]);

  const totalJourneySeconds = useMemo(
    () => segmentDurations.reduce((sum, duration) => sum + duration, 0),
    [segmentDurations]
  );

  const publishTrackingUpdate = (nextProgress: number, elapsedSeconds: number, nextStopIndex: number) => {
    if (!onTrackingUpdate) return;

    const completedSegments = segmentDurations.reduce<number[]>((totals, duration, index) => {
      totals.push((totals[index - 1] || 0) + duration);
      return totals;
    }, []);

    const actualTimes: Record<string, string> = {};
    trip.stops.forEach((stop, index) => {
      const stopElapsed = index === 0 ? 0 : completedSegments[index - 1];
      const hasDeparted = nextProgress > 0 || elapsedSeconds > 0;
      const hasReachedStop = index === 0 ? hasDeparted : elapsedSeconds >= (stopElapsed ?? Infinity);
      if (hasReachedStop) {
        actualTimes[stop.id] = formatJourneyClock(
          trip.departureTime,
          Number.isFinite(stopElapsed) ? stopElapsed : elapsedSeconds
        ).replace(' IST', '');
      }
    });

    const safeStopIndex = Math.max(0, Math.min(trip.stops.length - 1, nextStopIndex));
    setCurrentStopIndex(safeStopIndex);

    onTrackingUpdate({
      progress: nextProgress,
      clockTime: formatJourneyClock(trip.departureTime, elapsedSeconds),
      currentStopIndex: safeStopIndex,
      status: elapsedSeconds <= 0 && nextProgress <= 0
        ? 'NOT STARTED'
        : nextProgress >= 1
          ? 'COMPLETED'
          : 'RUNNING',
      actualTimes
    });
  };

  // Convert the current wall-clock time into a position on the scheduled route.
  const getTimetableSnapshot = () => {
    const todayInKolkata = getKolkataDateString();
    const journeyDate = selectedDate || todayInKolkata;

    // Keep a future-dated journey at its starting stop until that date arrives.
    if (journeyDate > todayInKolkata) {
      return {
        progress: 0,
        elapsedSeconds: 0,
        segmentIndex: 0,
        segmentElapsedSeconds: 0,
        currentStopIndex: 0,
        status: 'NOT STARTED' as const,
        clockTime: formatClockSeconds(getKolkataTimeSeconds()),
        actualTimes: {} as Record<string, string>
      };
    }

    const nowSeconds = getKolkataTimeSeconds();
    const departureSeconds = clockToMinutes(trip.departureTime) * 60;
    let elapsedSeconds = nowSeconds - departureSeconds;
    // If a scheduled trip departed late yesterday and is still running after midnight,
    // treat the clock as the following day. A negative gap under 12 hours is a future trip.
    if (elapsedSeconds < -12 * 3600) elapsedSeconds += 24 * 3600;

    if (elapsedSeconds < 0) {
      return {
        progress: 0,
        elapsedSeconds: 0,
        segmentIndex: 0,
        segmentElapsedSeconds: 0,
        currentStopIndex: 0,
        status: 'NOT STARTED' as const,
        clockTime: formatClockSeconds(nowSeconds),
        actualTimes: {} as Record<string, string>
      };
    }

    if (elapsedSeconds >= totalJourneySeconds || segmentDurations.length === 0) {
      const actualTimes: Record<string, string> = {};
      trip.stops.forEach(stop => {
        actualTimes[stop.id] = stop.predictedTime;
      });
      return {
        progress: 1,
        elapsedSeconds: totalJourneySeconds,
        segmentIndex: Math.max(0, segmentDurations.length - 1),
        segmentElapsedSeconds: segmentDurations[segmentDurations.length - 1] || 0,
        currentStopIndex: Math.max(0, trip.stops.length - 1),
        status: 'COMPLETED' as const,
        clockTime: formatClockSeconds(nowSeconds),
        actualTimes
      };
    }

    let remaining = elapsedSeconds;
    let segmentIndex = 0;
    while (segmentIndex < segmentDurations.length - 1 && remaining >= segmentDurations[segmentIndex]) {
      remaining -= segmentDurations[segmentIndex];
      segmentIndex += 1;
    }
    const segmentDuration = segmentDurations[segmentIndex] || 1;
    const segmentRatio = Math.max(0, Math.min(1, remaining / segmentDuration));
    const completedDistance = segmentLengths.lengths
      .slice(0, segmentIndex)
      .reduce((sum, length) => sum + length, 0);
    const currentDistance = completedDistance +
      (segmentLengths.lengths[segmentIndex] || 0) * segmentRatio;
    const nextProgress = segmentLengths.total > 0 ? currentDistance / segmentLengths.total : 0;
    const actualTimes: Record<string, string> = {};
    trip.stops.forEach((stop, index) => {
      if (index <= segmentIndex) {
        actualTimes[stop.id] = stop.predictedTime;
      }
    });

    return {
      progress: Math.max(0, Math.min(1, nextProgress)),
      elapsedSeconds,
      segmentIndex,
      segmentElapsedSeconds: remaining,
      currentStopIndex: Math.min(trip.stops.length - 1, segmentIndex + 1),
      status: 'RUNNING' as const,
      clockTime: formatClockSeconds(nowSeconds),
      actualTimes
    };
  };


  // Convert the current segment position into the route's distance-based progress value.
  const updateProgressFromAnimation = (segmentIndex: number, segmentRatio: number) => {
    if (segmentLengths.total <= 0 || segmentLengths.lengths.length === 0) {
      setProgress(0);
      return;
    }

    const completedDistance = segmentLengths.lengths
      .slice(0, segmentIndex)
      .reduce((sum, length) => sum + length, 0);
    const currentDistance =
      completedDistance +
      (segmentLengths.lengths[segmentIndex] || 0) * Math.max(0, Math.min(1, segmentRatio));

    setProgress(Math.max(0, Math.min(1, currentDistance / segmentLengths.total)));
  };

  // Find the bus position and direction from the current route progress.
  const currentBusState = useMemo(() => {
    if (routePoints.length < 2) {
      return { x: 750, y: 650, angle: 0, speed: 0 };
    }

    const targetDistance = progress * segmentLengths.total;
    let accumulated = 0;
    let segmentIndex = 0;
    let segmentRatio = 0;

    for (let i = 0; i < segmentLengths.lengths.length; i++) {
      const segmentLength = segmentLengths.lengths[i];
      if (
        accumulated + segmentLength >= targetDistance ||
        i === segmentLengths.lengths.length - 1
      ) {
        segmentIndex = i;
        segmentRatio =
          segmentLength > 0
            ? Math.max(0, Math.min(1, (targetDistance - accumulated) / segmentLength))
            : 0;
        break;
      }
      accumulated += segmentLength;
    }

    const first = routePoints[segmentIndex];
    const second = routePoints[segmentIndex + 1] || first;
    const x = first.x + (second.x - first.x) * segmentRatio;
    const y = first.y + (second.y - first.y) * segmentRatio;
    const angle = (Math.atan2(second.y - first.y, second.x - first.x) * 180) / Math.PI + 90;

    const averageSpeed =
      totalJourneySeconds > 0
        ? (trip.distanceKm / totalJourneySeconds) * 3600
        : 0;

    return { x, y, angle, speed: isAtStop ? 0 : averageSpeed };
  }, [progress, routePoints, segmentLengths, totalJourneySeconds, trip.distanceKm, isAtStop]);

  // Timetable-driven animation. Travel advances at 1x or 5x; each intermediate stop
  // pauses the visual bus for 4 real seconds. That pause does not modify stop times.
  useEffect(() => {
    let animationId: number;
    let lastFrameTime = performance.now();

    const tick = (now: number) => {
      const deltaSeconds = Math.min((now - lastFrameTime) / 1000, 0.1);
      lastFrameTime = now;

      if (isPlaying && trip.stops.length >= 2) {
        const state = animationStateRef.current;
        let remainingRealSeconds = deltaSeconds;
        let reachedDestination = false;

        while (remainingRealSeconds > 0 && !reachedDestination) {
          if (state.dwellRemainingSeconds > 0) {
            const dwellUsed = Math.min(
              remainingRealSeconds,
              state.dwellRemainingSeconds
            );
            state.dwellRemainingSeconds -= dwellUsed;
            remainingRealSeconds -= dwellUsed;

            if (state.dwellRemainingSeconds <= 0.0001) {
              state.dwellRemainingSeconds = 0;
              state.segmentIndex += 1;
              state.segmentElapsedSeconds = 0;
              if (state.segmentIndex >= segmentDurations.length) {
                reachedDestination = true;
              }
            }
          } else {
            const segmentDuration = segmentDurations[state.segmentIndex] || 1;
            const segmentRemaining = Math.max(
              0,
              segmentDuration - state.segmentElapsedSeconds
            );
            const simulatedAvailable = remainingRealSeconds * speedMultiplier;

            if (simulatedAvailable >= segmentRemaining) {
              const realTimeUsed = segmentRemaining / speedMultiplier;
              state.elapsedJourneySeconds += segmentRemaining;
              state.segmentElapsedSeconds = segmentDuration;
              remainingRealSeconds -= realTimeUsed;

              if (state.segmentIndex < segmentDurations.length - 1) {
                // Arrived at an intermediate stop: hold the marker for 4 seconds.
                state.dwellRemainingSeconds = STOP_DWELL_SECONDS;
                setIsAtStop(true);
              } else {
                reachedDestination = true;
              }
            } else {
              state.segmentElapsedSeconds += simulatedAvailable;
              state.elapsedJourneySeconds += simulatedAvailable;
              remainingRealSeconds = 0;
            }
          }
        }

        if (reachedDestination) {
          updateProgressFromAnimation(segmentDurations.length - 1, 1);
          setIsAtStop(false);
          setClockTime(formatJourneyClock(trip.departureTime, totalJourneySeconds));
          publishTrackingUpdate(1, totalJourneySeconds, trip.stops.length - 1);
          setIsPlaying(false);
        } else {
          const segmentDuration = segmentDurations[state.segmentIndex] || 1;
          const segmentRatio =
            state.dwellRemainingSeconds > 0
              ? 1
              : state.segmentElapsedSeconds / segmentDuration;

          updateProgressFromAnimation(state.segmentIndex, segmentRatio);
          setIsAtStop(state.dwellRemainingSeconds > 0);
          setClockTime(
            formatJourneyClock(trip.departureTime, state.elapsedJourneySeconds)
          );
          const completedDistance = segmentLengths.lengths.slice(0, state.segmentIndex).reduce((sum, value) => sum + value, 0);
          const currentDistance = completedDistance + (segmentLengths.lengths[state.segmentIndex] || 0) * Math.max(0, Math.min(1, segmentRatio));
          const nextProgress = segmentLengths.total > 0 ? currentDistance / segmentLengths.total : 0;
          publishTrackingUpdate(
            nextProgress,
            state.elapsedJourneySeconds,
            Math.min(trip.stops.length - 1, state.segmentIndex + 1)
          );
        }
      }

      animationId = requestAnimationFrame(tick);
    };

    animationId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animationId);
  }, [
    isPlaying,
    speedMultiplier,
    trip.id,
    trip.departureTime,
    trip.stops.length,
    segmentDurations,
    totalJourneySeconds,
    segmentLengths
  ]);

  // On opening a trip, follow the real Kolkata clock and place the bus at its
  // timetable-derived position. This also updates status and stop times every second.
  useEffect(() => {
    if (isManualMode) return;

    const syncToCurrentTime = () => {
      const snapshot = getTimetableSnapshot();
      animationStateRef.current = {
        segmentIndex: snapshot.segmentIndex,
        segmentElapsedSeconds: snapshot.segmentElapsedSeconds,
        dwellRemainingSeconds: 0,
        elapsedJourneySeconds: snapshot.elapsedSeconds
      };
      setProgress(snapshot.progress);
      setCurrentStopIndex(snapshot.currentStopIndex);
      setIsAtStop(false);
      setClockTime(snapshot.clockTime);
      onTrackingUpdate?.({
        progress: snapshot.progress,
        clockTime: snapshot.clockTime,
        currentStopIndex: snapshot.currentStopIndex,
        status: snapshot.status,
        actualTimes: snapshot.actualTimes
      });
    };

    setIsPlaying(false);
    syncToCurrentTime();
    const intervalId = window.setInterval(syncToCurrentTime, 1000);
    return () => window.clearInterval(intervalId);
  }, [trip.id, trip.departureTime, trip.stops, selectedDate, isManualMode, onTrackingUpdate, totalJourneySeconds, segmentDurations, segmentLengths]);


  // Fullscreen handler
  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().then(() => setIsFullscreen(true)).catch(() => {});
    } else {
      document.exitFullscreen().then(() => setIsFullscreen(false)).catch(() => {});
    }
  };

  // Center on Bus
  const centerOnBus = () => {
    setZoomLevel(1.3);
    setPanOffset({
      x: (500 - currentBusState.x) * 0.4,
      y: (500 - currentBusState.y) * 0.4
    });
  };

  const resetView = () => {
    setZoomLevel(1);
    setPanOffset({ x: 0, y: 0 });
  };

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full min-h-[580px] bg-[#080d18] rounded-2xl border border-slate-800/80 overflow-hidden shadow-2xl flex flex-col select-none"
    >
      {/* Top Map HUD Bar (Matching reference image) */}
      <div className="absolute top-4 left-4 right-4 z-20 flex items-center justify-between pointer-events-none">
        <div className="flex items-center gap-2 pointer-events-auto">
          {/* Simulation mode indicator */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/90 backdrop-blur-md border border-cyan-500/30 text-xs font-semibold text-cyan-400 shadow-lg tracking-wider">
            <RotateCcw className="w-3.5 h-3.5 text-cyan-400" />
            <span className="font-mono">
              {!isManualMode ? 'TIMETABLE SYNC' : speedMultiplier === 1 ? 'SIMULATION 1X' : 'ACCELERATED 5X'}
            </span>
          </div>

          {/* IST Time readout */}
          <div className="px-3 py-1.5 rounded-lg bg-slate-900/90 backdrop-blur-md border border-slate-800 text-xs font-mono font-medium text-slate-300 shadow-lg tabular-nums">
            {clockTime}
          </div>
          {isAtStop && (
            <div className="px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-xs font-mono font-semibold text-amber-300">
              STOP · WAITING 4s
            </div>
          )}
        </div>

        {/* Top Right Map Actions */}
        <div className="flex items-center gap-2 pointer-events-auto">
          <button
            onClick={centerOnBus}
            title="Center on Bus"
            className="p-2 rounded-lg bg-slate-900/80 hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-cyan-400 backdrop-blur-md transition-colors"
          >
            <Compass className="w-4 h-4" />
          </button>
          <button
            onClick={() => setZoomLevel(z => Math.min(2.2, z + 0.2))}
            title="Zoom In"
            className="p-2 rounded-lg bg-slate-900/80 hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-cyan-400 backdrop-blur-md transition-colors"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={() => setZoomLevel(z => Math.max(0.8, z - 0.2))}
            title="Zoom Out"
            className="p-2 rounded-lg bg-slate-900/80 hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-cyan-400 backdrop-blur-md transition-colors"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={toggleFullscreen}
            title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
            className="p-2 rounded-lg bg-slate-900/80 hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-cyan-400 backdrop-blur-md transition-colors"
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Main SVG Vector Transit Cartography Canvas */}
      <div className="relative flex-1 w-full h-full overflow-hidden cursor-grab active:cursor-grabbing">
        <svg
          viewBox="0 0 1000 1000"
          className="w-full h-full object-cover transition-transform duration-300 ease-out"
          style={{
            transform: `scale(${zoomLevel}) translate(${panOffset.x}px, ${panOffset.y}px)`,
            transformOrigin: '50% 50%'
          }}
        >
          <defs>
            {/* Neon Glow Filter for Cyan Route */}
            <filter id="cyanGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

            {/* Headlight Projection Beam Gradient */}
            <linearGradient id="headlightBeam" x1="0%" y1="100%" x2="0%" y2="0%">
              <stop offset="0%" stopColor="#00f5ff" stopOpacity="0.75" />
              <stop offset="40%" stopColor="#38bdf8" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#38bdf8" stopOpacity="0" />
            </linearGradient>

            {/* Arabian Sea Water Gradient */}
            <linearGradient id="seaGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#040914" />
              <stop offset="60%" stopColor="#071224" />
              <stop offset="100%" stopColor="#0a1a33" />
            </linearGradient>

            {/* Landmass Shading */}
            <linearGradient id="landGradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#080e1a" />
              <stop offset="50%" stopColor="#0a1222" />
              <stop offset="100%" stopColor="#0d182e" />
            </linearGradient>
          </defs>

          {/* Background: Base Canvas */}
          <rect width="1000" height="1000" fill="url(#landGradient)" />

          {/* Topographic Water / Arabian Sea on Western Coast */}
          <path
            d="M 0 0 L 520 0 Q 510 180 540 320 T 590 540 Q 640 680 670 820 L 680 1000 L 0 1000 Z"
            fill="url(#seaGradient)"
            opacity="0.85"
          />

          {/* Gentle Sea Waves & Contour Coastline lines */}
          <path
            d="M 0 120 Q 250 140 515 150"
            stroke="#0e2444"
            strokeWidth="1.5"
            strokeDasharray="4 8"
            fill="none"
          />
          <path
            d="M 0 340 Q 300 360 550 380"
            stroke="#0e2444"
            strokeWidth="1.5"
            strokeDasharray="4 8"
            fill="none"
          />
          <path
            d="M 0 620 Q 340 640 620 660"
            stroke="#0e2444"
            strokeWidth="1.5"
            strokeDasharray="4 8"
            fill="none"
          />
          <text
            x="140"
            y="480"
            fill="#1e3a5f"
            fontSize="18"
            fontFamily="Plus Jakarta Sans, sans-serif"
            fontWeight="700"
            letterSpacing="6"
            opacity="0.5"
            transform="rotate(-75 140 480)"
          >
            ARABIAN SEA (LAKSHADWEEP SEA)
          </text>

          {/* Coastal Shoreline Contour Polyline */}
          <path
            d="M 520 0 Q 510 180 540 320 T 590 540 Q 640 680 670 820 L 680 1000"
            stroke="#163860"
            strokeWidth="2.5"
            fill="none"
          />

          {/* Kozhikode Urban Road Network Grid (Dark slate subtle network) */}
          <g opacity="0.35">
            {/* NH 66 Parallel Bypass Arterials */}
            <path d="M 680 100 L 730 450 L 780 720 L 860 1000" stroke="#1e293b" strokeWidth="8" fill="none" />
            <path d="M 680 100 L 730 450 L 780 720 L 860 1000" stroke="#334155" strokeWidth="1.5" fill="none" />

            {/* Mavoor Road to Medical College & Kunnamangalam */}
            <path d="M 790 810 L 870 780 L 960 760" stroke="#1e293b" strokeWidth="7" fill="none" />
            <path d="M 790 810 L 870 780 L 960 760" stroke="#334155" strokeWidth="1.5" fill="none" />

            {/* Mini Bypass connecting Thondayad to Puthiyangadi */}
            <path d="M 820 800 L 780 710 L 740 640" stroke="#1e293b" strokeWidth="5" fill="none" />

            {/* Wayanad Road (NH 766) towards Thamarassery */}
            <path d="M 870 780 L 990 680" stroke="#1e293b" strokeWidth="5" fill="none" />

            {/* Feroke & Ramanattukara South Corridor */}
            <path d="M 790 810 L 820 880 L 860 970" stroke="#1e293b" strokeWidth="6" fill="none" />

            {/* Secondary Town Roads */}
            <path d="M 610 270 L 740 250" stroke="#1e293b" strokeWidth="3" fill="none" />
            <path d="M 640 405 L 750 410" stroke="#1e293b" strokeWidth="3" fill="none" />
            <path d="M 710 520 L 820 530" stroke="#1e293b" strokeWidth="3" fill="none" />
            <path d="M 750 680 L 830 670" stroke="#1e293b" strokeWidth="3" fill="none" />
            <path d="M 790 810 L 720 830" stroke="#1e293b" strokeWidth="3" fill="none" />
          </g>

          {/* Active Bus Route Polyline (Glowing Neon Cyan) */}
          <g filter="url(#cyanGlow)">
            {/* Outer Cyan Soft Halo Line */}
            <polyline
              points={routePoints.map(p => `${p.x},${p.y}`).join(' ')}
              fill="none"
              stroke="#00f5ff"
              strokeWidth="6"
              strokeLinecap="round"
              strokeLinejoin="round"
              opacity="0.5"
            />
            {/* Inner Vibrant Core Cyan Line */}
            <polyline
              points={routePoints.map(p => `${p.x},${p.y}`).join(' ')}
              fill="none"
              stroke="#ffffff"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              opacity="0.95"
            />
          </g>

          {/* Stop Nodes & Text Labels (Matching reference image) */}
          {trip.stops.map((stop, idx) => {
            const isTarget = idx === currentStopIndex;
            const isPassed = idx < currentStopIndex;

            return (
              <g
                key={stop.id}
                className="cursor-pointer group"
                onClick={() => onStopSelect && onStopSelect(stop.id)}
              >
                {/* Halo around current active target stop */}
                {isTarget && (
                  <circle
                    cx={stop.x}
                    cy={stop.y}
                    r="12"
                    fill="none"
                    stroke="#00f5ff"
                    strokeWidth="1.5"
                    opacity="0.6"
                    className="animate-ping"
                  />
                )}

                {/* Stop Node Dot */}
                <circle
                  cx={stop.x}
                  cy={stop.y}
                  r={isTarget ? 6.5 : 5}
                  fill={isTarget ? '#00f5ff' : isPassed ? '#38bdf8' : '#1e293b'}
                  stroke={isTarget ? '#ffffff' : '#080d18'}
                  strokeWidth="2"
                  filter="drop-shadow(0 0 6px rgba(0, 245, 255, 0.8))"
                />

                {/* Stop Typography Label */}
                <g transform={`translate(${stop.x + 14}, ${stop.y + 4})`}>
                  {/* Subtle dark backing pill for text contrast */}
                  <rect
                    x="-4"
                    y="-12"
                    width={stop.name.length * 8 + 10}
                    height="18"
                    rx="4"
                    fill="#080e1ac0"
                    stroke="#1e293b80"
                    strokeWidth="0.8"
                    className="backdrop-blur-sm"
                  />
                  <text
                    x="0"
                    y="0"
                    fill={isTarget ? '#00f5ff' : '#cbd5e1'}
                    fontSize="11.5"
                    fontFamily="Plus Jakarta Sans, sans-serif"
                    fontWeight={isTarget ? '700' : '500'}
                    className="group-hover:fill-cyan-300 transition-colors"
                  >
                    {stop.name}
                  </text>
                </g>
              </g>
            );
          })}

          {/* The High-Detail Moving Bus Marker */}
          <BusMarker
            x={currentBusState.x}
            y={currentBusState.y}
            headingAngle={currentBusState.angle}
            speedKmH={currentBusState.speed}
            serviceClass={trip.serviceClass}
            busNumber={trip.id.replace('BUS', '')}
            isLive={progress > 0 && progress < 1 && (!isManualMode || (isPlaying && !isAtStop))}
          />
        </svg>
      </div>

    </div>
  );
};
