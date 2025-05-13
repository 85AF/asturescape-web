import React from 'react';
import logo from '../assets/imagenes/asturescape-logo.png';

interface LogoProps {
  className?: string;
}

const Logo: React.FC<LogoProps> = ({ className = '' }) => {
  return (
    <div className={`flex items-center gap-2 ${className}`}>
    <div className="w-32 h-16 md:w-48 md:h-20 lg:w-64 lg:h-24">
      <img src={logo} alt="AsturEscape logo" className="w-full h-full object-contain" />
    </div>
  </div>
  );
};

export default Logo;