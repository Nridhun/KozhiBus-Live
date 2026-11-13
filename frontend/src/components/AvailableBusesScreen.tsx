
import React, { useEffect, useMemo, useState } from 'react';
import {
  Bus,
  ArrowLeft,
  Navigation,
  Clock,
  Filter,
  ArrowUpDown,
  Sparkles,
  AlertCircle,
  RefreshCw
} from 'lucide-react';
import { TIME_SLOTS } from '../data/transitData';

interface AvailableBusesScreenProps {
  searchQuery: {
    origin: string;
    destination: string;
    slotId: number | 'all';
    date: string;
  };
  onBackToSearch: () => void;
  onTrackBus: (trip: any) => void;
}

interface ApiBus {
  journey_id: string;
  trip_id: string;
  bus_id: string;
  bus_type: string;
  route_id: string;
  origin: string;
  destination: string;
  departure_time: string;
  scheduled_arrival: string;
  predicted_arrival: string;
  distance_km: number;
  scheduled_duration_min: number;
  traffic_level: string;
  weather_condition: string;
  predicted_remaining_delay_min: number;
  prediction_status: string;
  data_type: string;
}

export const AvailableBusesScreen: React.FC<AvailableBusesScreenProps> = ({
  searchQuery,
  onBackToSearch,
  onTrackBus
}) => {
  const [buses, setBuses] = useState<ApiBus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  const [selectedService, setSelectedService] = useState('all');
  const [activeSlotFilter, setActiveSlotFilter] =
    useState<number | 'all'>(searchQuery.slotId);

  const [sortBy, setSortBy] = useState<
    'departure' | 'duration' | 'delay'
  >('departure');

  useEffect(() => {
    setActiveSlotFilter(searchQuery.slotId);
  }, [searchQuery.slotId]);



  useEffect(() => {


    const controller = new AbortController();

    const fetchBuses = async () => {
      setLoading(true);
      setError(null);

      try {
        const selectedSlot = TIME_SLOTS.find(
          slot => slot.id === activeSlotFilter
        );

        const startHour =
          activeSlotFilter === 'all'
            ? 0
            : selectedSlot?.startHour ?? 0;

        const startTime = startHour * 60;
        const endTime =
          activeSlotFilter === 'all'
            ? 1439
            : Math.min(startTime + 120, 1439);

        const params = new URLSearchParams({
          origin: searchQuery.origin,
          destination: searchQuery.destination,
          date: searchQuery.date,
          start_time: String(startTime),
          end_time: String(endTime)
        });

        const response = await fetch(
          `http://127.0.0.1:8000/api/buses?${params.toString()}`,
          { signal: controller.signal }
        );

        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }

        const data = await response.json();

        setBuses(Array.isArray(data.buses) ? data.buses : []);

      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          return;
        }

        console.error('Bus fetching error:', err);
        setError('Unable to load buses. Please check the backend API.');
        setBuses([]);
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    };

    fetchBuses();

    return () => controller.abort();
  },  [
  searchQuery.origin,
  searchQuery.destination,
  searchQuery.date,
  activeSlotFilter,
  retryCount
]);

  const filteredTrips = useMemo(() => {
    return buses
      .filter(bus => {
        if (
          selectedService !== 'all' &&
          bus.bus_type.toUpperCase() !== selectedService
        ) {
          return false;
        }

        return true;
      })
      .sort((a, b) => {
        if (sortBy === 'departure') {
          return a.departure_time.localeCompare(b.departure_time);
        }

        if (sortBy === 'duration') {
          return a.scheduled_duration_min - b.scheduled_duration_min;
        }

        return (
          a.predicted_remaining_delay_min -
          b.predicted_remaining_delay_min
        );
      });
  }, [buses, selectedService, sortBy]);

  const formatDuration = (minutes: number) => {
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;

    if (hours === 0) return `${remainingMinutes} min`;

    return `${hours}h ${remainingMinutes}m`;
  };

  const getDelayStyle = (delay: number) => {
    if (delay <= 0) return 'text-emerald-400';
    if (delay <= 3) return 'text-cyan-400';
    return 'text-amber-400';
  };

  const formatDelay = (delay: number) => {
    if (delay < 0) return `${Math.abs(delay)} min early`;
    if (delay === 0) return 'On time';
    return `+${delay.toFixed(1)} min`;
  };

  return (
    <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">

        <div className="flex items-center gap-4">
          <button
            onClick={onBackToSearch}
            className="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 flex items-center gap-2 text-xs"
          >
            <ArrowLeft className="w-4 h-4" />
            Search
          </button>

          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-white">
              {searchQuery.origin}
              <span className="text-cyan-400"> → </span>
              {searchQuery.destination}
            </h1>

            <div className="text-xs text-slate-400 mt-1 font-mono">
              Date: {searchQuery.date}
              {' · '}
              {loading ? 'Searching buses...' : `${filteredTrips.length} buses found`}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 text-xs">

          <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 rounded-lg p-2">
            <Filter className="w-3.5 h-3.5 text-slate-400" />

            <select
              value={selectedService}
              onChange={e => setSelectedService(e.target.value)}
              className="bg-transparent text-slate-200 outline-none"
            >
              <option value="all">All Services</option>
              <option value="ORDINARY">Ordinary</option>
              <option value="LIMITED STOP">Limited Stop</option>
              <option value="SUPER FAST">Super Fast</option>
              <option value="FAST PASSENGER">Fast Passenger</option>
            </select>
          </div>

          <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 rounded-lg p-2">
            <ArrowUpDown className="w-3.5 h-3.5 text-slate-400" />

            <select
              value={sortBy}
              onChange={e => setSortBy(e.target.value as typeof sortBy)}
              className="bg-transparent text-slate-200 outline-none"
            >
              <option value="departure">Departure time</option>
              <option value="duration">Duration</option>
              <option value="delay">Least predicted delay</option>
            </select>
          </div>
        </div>
      </div>

      {/* 24-hour time slots */}
      <div className="bg-[#0b1324] border border-slate-800 rounded-2xl p-4">

        <div className="flex items-center justify-between mb-3">
          <span className="flex items-center gap-2 text-xs font-semibold text-cyan-400">
            <Clock className="w-4 h-4" />
            Select Departure Time
          </span>

          <span className="text-xs text-slate-500">
            24 hours · 2-hour slots
          </span>
        </div>

        <div className="flex items-center gap-2 overflow-x-auto pb-2">

          <button
            onClick={() => setActiveSlotFilter('all')}
            className={`px-4 py-2 rounded-xl text-xs whitespace-nowrap ${
              activeSlotFilter === 'all'
                ? 'bg-cyan-500 text-slate-950 font-bold'
                : 'bg-slate-900 text-slate-300 border border-slate-800'
            }`}
          >
            All 24 Hours
          </button>

          {TIME_SLOTS.map(slot => (
            <button
              key={slot.id}
              onClick={() => setActiveSlotFilter(slot.id)}
              className={`px-4 py-2 rounded-xl text-xs whitespace-nowrap ${
                activeSlotFilter === slot.id
                  ? 'bg-cyan-500 text-slate-950 font-bold'
                  : 'bg-slate-900 text-slate-300 border border-slate-800'
              }`}
            >
              {slot.label}
            </button>
          ))}
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="bg-[#0b1324] border border-slate-800 rounded-2xl p-10 text-center">
          <RefreshCw className="w-7 h-7 text-cyan-400 animate-spin mx-auto mb-3" />
          <p className="text-slate-300 text-sm">Finding available buses...</p>
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div className="bg-[#0b1324] border border-red-500/30 rounded-2xl p-6 text-center">
          <AlertCircle className="w-7 h-7 text-red-400 mx-auto mb-3" />
          <p className="text-red-300 text-sm">{error}</p>

          <button
            onClick={() => setActiveSlotFilter(current => current)}


            className="mt-3 text-cyan-400 text-xs underline"
          >
            Try again
          </button>
        </div>
      )}

      {/* No buses */}
      {!loading && !error && filteredTrips.length === 0 && (
        <div className="bg-[#0b1324] border border-slate-800 rounded-2xl p-10 text-center">
          <Bus className="w-9 h-9 text-slate-500 mx-auto mb-3" />
          <h3 className="text-white font-semibold">
            No buses found
          </h3>
          <p className="text-slate-400 text-xs mt-2">
            No matching buses were returned for this route and time slot.
          </p>
          <button
            onClick={() => setActiveSlotFilter('all')}
            className="mt-4 px-4 py-2 bg-slate-800 text-cyan-400 rounded-lg text-xs"
          >
            Show All 24 Hours
          </button>
        </div>
      )}

      {/* Bus results */}
      {!loading && !error && filteredTrips.length > 0 && (
        <div className="space-y-4">

          {filteredTrips.map((trip, index) => (
  <div
    key={`${trip.journey_id}-${trip.trip_id}-${index}`}
    role="button"
    tabIndex={0}
    aria-label={`Track bus ${trip.bus_id}`}
    onClick={() => onTrackBus(trip)}
    onKeyDown={(event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        onTrackBus(trip);
      }
    }}
    className="bg-[#0b1324] border border-slate-800 rounded-2xl p-5 space-y-4 cursor-pointer hover:border-cyan-500/60 hover:bg-[#101b30] transition-all focus:outline-none focus:ring-2 focus:ring-cyan-500"
  >

              {/* Bus heading */}
              <div className="flex flex-wrap items-start justify-between gap-3">

                <div>
                  <div className="flex items-center gap-2">
                    <Bus className="w-5 h-5 text-cyan-400" />

                    <span className="text-lg font-bold text-white font-mono">
                      {trip.bus_id}
                    </span>
                  </div>

                  <p className="text-xs text-slate-400 mt-1">
                    {trip.bus_type} · Route {trip.route_id}
                  </p>

                  <p className="text-[11px] text-slate-500 mt-1">
                    Trip: {trip.trip_id}
                  </p>
                </div>

                <span className="px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-[10px] font-semibold">
                  {trip.prediction_status}
                </span>
              </div>

              {/* Timing */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 rounded-xl bg-slate-900/80 border border-slate-800">

                <div>
                  <p className="text-[10px] text-slate-500 uppercase">
                    Departure
                  </p>
                  <p className="text-base text-white font-bold font-mono mt-1">
                    {trip.departure_time}
                  </p>
                </div>

                <div>
                  <p className="text-[10px] text-slate-500 uppercase">
                    Scheduled Arrival
                  </p>
                  <p className="text-base text-white font-bold font-mono mt-1">
                    {trip.scheduled_arrival}
                  </p>
                </div>

                <div>
                  <p className="text-[10px] text-slate-500 uppercase">
                    ML Predicted Arrival
                  </p>
                  <p className="text-base text-cyan-400 font-bold font-mono mt-1">
                    {trip.predicted_arrival}
                  </p>
                </div>

                <div>
                  <p className="text-[10px] text-slate-500 uppercase">
                    Predicted Remaining Delay
                  </p>
                  <p className={`text-base font-bold font-mono mt-1 ${getDelayStyle(trip.predicted_remaining_delay_min)}`}>
                    {formatDelay(trip.predicted_remaining_delay_min)}
                  </p>
                </div>
              </div>

              {/* Other information */}
              <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs text-slate-400">
                <span>
                  <Clock className="w-3.5 h-3.5 inline mr-1 text-cyan-400" />
                  {formatDuration(trip.scheduled_duration_min)}
                </span>

                <span>
                  Distance: {trip.distance_km} km
                </span>

                <span>
                  Traffic: {trip.traffic_level}
                </span>

                <span>
                  Weather: {trip.weather_condition}
                </span>
              </div>

              {/* Data information */}
              <div className="flex items-center gap-2 text-[10px] text-amber-400 border-t border-slate-800 pt-3">
                <Sparkles className="w-3.5 h-3.5" />
                {trip.data_type === 'TEMPORARY_SIMULATION'
                  ? 'Temporary simulated journey based on historical data'
                  : 'Historical dataset result'}
              </div>

              {/* Tracking limitation */}
              <div className="flex items-center justify-between gap-3 border-t border-slate-800 pt-3">
                <span className="text-[11px] text-slate-500">
                  Live GPS tracking is not connected yet.
                </span>

                <button
                  type="button"
                  disabled
                  title="Tracking requires stop coordinates and live position data"
                  className="px-4 py-2 rounded-xl bg-slate-800 text-slate-500 font-bold text-xs flex items-center gap-2 cursor-not-allowed"
                >
                  <Navigation className="w-3.5 h-3.5" />
                  Tracking unavailable
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
