export type ServiceClass =
  | 'FAST PASSENGER'
  | 'KSRTC SWIFT AC'
  | 'CITY ORDINARY'
  | 'MINNAL DELUXE'
  | 'PRIVATE STAGE';

export interface RouteStop {
  id: string;
  name: string;
  shortName?: string;
  x: number;
  y: number;
  scheduledTime: string;
  predictedTime: string;
  distanceKm: number;
  status: 'passed' | 'current' | 'upcoming';
  platform?: string;
}

export interface MLDelayFactor {
  factor: string;
  impactMinutes: number;
  confidence: number;
  description: string;
  level: 'low' | 'moderate' | 'high';
}

export interface BusTrip {
  id: string;
  routeCode: string;
  operator: string;
  serviceClass: ServiceClass;
  origin: string;
  destination: string;
  via: string;
  departureTime: string;
  departureSlot: string;
  departureSlotId: number;
  scheduledArrival: string;
  predictedArrival: string;
  duration: string;
  distanceKm: number;
  delayMinutes: number;
  trafficStatus: 'Low' | 'Moderate' | 'Heavy';
  weatherStatus: string;
  fare: number;
  currentStopIndex: number;
  headingText: string;
  pickupStatus?: {
    stop: string;
    status: 'Departed' | 'Boarding' | 'Scheduled';
  };
  dropStatus?: {
    stop: string;
    timeRemaining: string;
  };
  stops: RouteStop[];
  mlFactors: MLDelayFactor[];
}

export interface TimeSlot {
  id: number;
  label: string;
  startHour: number;
  period: 'Late Night' | 'Early Morning' | 'Morning Peak' | 'Midday' | 'Evening Peak' | 'Night';
}
