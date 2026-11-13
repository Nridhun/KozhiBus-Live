
import React from 'react';

interface BusMarkerProps {
  x: number;
  y: number;
  headingAngle: number;
  speedKmH?: number;
  serviceClass?: string;
  busNumber?: string;
  isLive?: boolean;
}

export const BusMarker: React.FC<BusMarkerProps> = ({
  x,
  y,
  headingAngle,
  speedKmH = 46,
  serviceClass = 'FAST PASSENGER',
  busNumber = '31',
  isLive = true
}) => {
  const isSwift = serviceClass.includes('SWIFT');
  const isMinnal = serviceClass.includes('MINNAL');

  const liveryColor = isSwift
    ? '#00f5ff'
    : isMinnal
      ? '#f59e0b'
      : '#38bdf8';

  return (
    <g
      transform={`translate(${x}, ${y})`}
      className="pointer-events-none select-none"
    >
      {/* Small radar pulse */}
      {isLive && (
        <circle
          r="23"
          fill="none"
          stroke={liveryColor}
          strokeWidth="1.5"
          opacity="0.35"
          className="animate-ping"
        />
      )}

      {/* Bus shadow */}
      <ellipse
        cx="0"
        cy="3"
        rx="13"
        ry="24"
        fill="#000000"
        opacity="0.65"
        filter="blur(3px)"
      />

      {/* Rotate and reduce bus size */}
      <g transform={`rotate(${headingAngle}) scale(0.58)`}>

        {/* Front headlights */}
        <path
          d="M -7 -23 L -15 -48 L 15 -48 L 7 -23 Z"
          fill={liveryColor}
          opacity="0.10"
        />

        {/* Wheels */}
        <rect x="-13" y="-17" width="4" height="11"
          rx="1.5" fill="#020617" stroke="#64748b" strokeWidth="0.8" />

        <rect x="9" y="-17" width="4" height="11"
          rx="1.5" fill="#020617" stroke="#64748b" strokeWidth="0.8" />

        <rect x="-13" y="10" width="4" height="11"
          rx="1.5" fill="#020617" stroke="#64748b" strokeWidth="0.8" />

        <rect x="9" y="10" width="4" height="11"
          rx="1.5" fill="#020617" stroke="#64748b" strokeWidth="0.8" />

        {/* Main bus body */}
        <rect
          x="-10"
          y="-25"
          width="20"
          height="51"
          rx="5"
          fill="#0c1729"
          stroke={liveryColor}
          strokeWidth="2"
          filter="drop-shadow(0 0 5px rgba(0,245,255,0.5))"
        />

        {/* Front windshield */}
        <path
          d="M -7 -20 Q 0 -24 7 -20 L 7 -12 L -7 -12 Z"
          fill="#7dd3fc"
          stroke="#bae6fd"
          strokeWidth="0.7"
        />

        {/* Front bumper */}
        <path
          d="M -7 -24 L 7 -24"
          stroke="#e2e8f0"
          strokeWidth="1.5"
          strokeLinecap="round"
        />

        {/* Passenger windows - left */}
        <g fill="#38bdf8" opacity="0.9">
          <rect x="-7.5" y="-8" width="4" height="7" rx="1" />
          <rect x="-7.5" y="1" width="4" height="7" rx="1" />
          <rect x="-7.5" y="10" width="4" height="7" rx="1" />
        </g>

        {/* Passenger windows - right */}
        <g fill="#38bdf8" opacity="0.9">
          <rect x="3.5" y="-8" width="4" height="7" rx="1" />
          <rect x="3.5" y="1" width="4" height="7" rx="1" />
          <rect x="3.5" y="10" width="4" height="7" rx="1" />
        </g>

        {/* Central roof */}
        <rect
          x="-2"
          y="-7"
          width="4"
          height="27"
          rx="1"
          fill="#1e293b"
          stroke="#475569"
          strokeWidth="0.6"
        />

        {/* Roof fleet number */}
        <text
          x="0"
          y="5"
          fill="#ffffff"
          fontSize="5"
          fontWeight="800"
          textAnchor="middle"
          dominantBaseline="central"
          fontFamily="monospace"
        >
          {busNumber}
        </text>

        {/* Front headlights */}
        <rect
          x="-7"
          y="-25"
          width="4"
          height="2"
          rx="1"
          fill="#ffffff"
          filter="drop-shadow(0 0 3px #00f5ff)"
        />

        <rect
          x="3"
          y="-25"
          width="4"
          height="2"
          rx="1"
          fill="#ffffff"
          filter="drop-shadow(0 0 3px #00f5ff)"
        />

        {/* Rear tail lights */}
        <rect
          x="-7"
          y="24"
          width="4"
          height="2"
          rx="0.8"
          fill="#ef4444"
          filter="drop-shadow(0 0 3px #ef4444)"
        />

        <rect
          x="3"
          y="24"
          width="4"
          height="2"
          rx="0.8"
          fill="#ef4444"
          filter="drop-shadow(0 0 3px #ef4444)"
        />

      </g>
    </g>
  );
};
