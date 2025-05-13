import React from 'react';
import escapeBg from '../assets/imagenes/escapeBg.jpg';

const Home: React.FC = () => {
  const scrollToReservation = () => {
    const element = document.getElementById('reservation');
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <section 
      id="home" 
      className="h-screen flex items-center justify-center relative"
      style={{
        backgroundImage: `linear-gradient(rgba(10, 59, 92, 0.8), rgba(10, 59, 92, 0.9)), url(${escapeBg})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center'
      }}
    >
      <div className="absolute inset-0 bg-gradient-to-b from-black/40 to-dark-blue/70"></div>
      
      <div className="container mx-auto px-4 text-center relative z-10">
        <h2 className="text-4xl md:text-6xl lg:text-7xl font-title font-extrabold mb-4 tracking-tight">
          ¿PUEDES <span className="text-secondary">ESCAPAR</span>?
        </h2>
        
        <p className="text-xl md:text-2xl font-title font-medium italic mb-8 text-white/90">
          Escápate a la aventura
        </p>
        
        <button 
          onClick={scrollToReservation}
          className="bg-secondary hover:bg-accent text-dark-blue font-bold py-3 px-8 rounded-lg transition-all duration-300 transform hover:scale-105 uppercase tracking-wide"
        >
          Reserva Ahora
        </button>
      </div>
      
      <div className="absolute bottom-8 left-1/2 transform -translate-x-1/2 animate-bounce">
        <svg 
          width="24" 
          height="24" 
          viewBox="0 0 24 24" 
          fill="none" 
          xmlns="http://www.w3.org/2000/svg"
          className="text-white"
        >
          <path 
            d="M12 5V19M12 19L5 12M12 19L19 12" 
            stroke="currentColor" 
            strokeWidth="2" 
            strokeLinecap="round" 
            strokeLinejoin="round"
          />
        </svg>
      </div>
    </section>
  );
};

export default Home;