import React, { useState } from 'react';
import imgPrision from '../assets/imagenes/4ERooms.jpg';
import imgBosque from '../assets/imagenes/5ERooms.jpg';

interface RoomProps {
  title: string;
  description: string;
  image: string;
  difficulty: number;
  players: string;
  time: string;
}

interface PricingCardProps {
  title: string;
  price: string;
  description: string;
  features: string[];
  isPopular?: boolean;
}

const RoomCard: React.FC<RoomProps> = ({ 
  title, 
  description, 
  image, 
  difficulty, 
  players, 
  time 
}) => {
  const [isHovered, setIsHovered] = useState(false);
  
  const renderDifficulty = () => {
    const dots = [];
    for (let i = 0; i < 5; i++) {
      dots.push(
        <div 
          key={i} 
          className={`w-2 h-2 rounded-full ${i < difficulty ? 'bg-accent' : 'bg-gray-600'}`}
        ></div>
      );
    }
    return dots;
  };

  return (
    <div 
      className="relative rounded-xl overflow-hidden group h-96 cursor-pointer"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className="absolute inset-0 bg-gradient-to-t from-black to-transparent z-10"></div>
      <img 
        src={image} 
        alt={title} 
        className={`w-full h-full object-cover transition-transform duration-700 ${isHovered ? 'scale-110' : 'scale-100'}`}
      />
      
      <div className="absolute bottom-0 left-0 right-0 p-6 z-20 transform transition-transform duration-500">
        <h3 className="text-2xl font-title font-bold mb-2 text-secondary">{title}</h3>
        
        <div className="flex items-center space-x-2 mb-2">
          <div className="flex space-x-1">
            {renderDifficulty()}
          </div>
          <span className="text-xs text-white/70">Dificultad</span>
        </div>
        
        <div className={`overflow-hidden transition-all duration-500 ${isHovered ? 'max-h-96 opacity-100' : 'max-h-0 opacity-0'}`}>
          <p className="text-white/90 mb-4">{description}</p>
          
          <div className="flex justify-between text-sm text-white/70">
            <span>🧩 {players}</span>
            <span>⏱️ {time}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

const PricingCard: React.FC<PricingCardProps> = ({
  title,
  price,
  description,
  features,
  isPopular = false
}) => {
  return (
    <div className={`relative rounded-xl overflow-hidden transition-all duration-300 transform hover:-translate-y-2 ${
      isPopular ? 'bg-accent/10 border-2 border-accent' : 'bg-dark-gray border border-gray-700'
    }`}>
      {isPopular && (
        <div className="absolute top-4 right-4">
          <span className="bg-accent text-white text-xs font-bold px-3 py-1 rounded-full">
            Más vendido
          </span>
        </div>
      )}
      
      <div className="p-8">
        <h3 className="text-xl font-title font-bold mb-2 text-secondary">{title}</h3>
        <div className="mb-4">
          <span className="text-4xl font-title font-extrabold text-white">{price}</span>
        </div>
        <p className="text-white/80 mb-6">{description}</p>
        
        <ul className="space-y-3 mb-8">
          {features.map((feature, index) => (
            <li key={index} className="flex items-center text-white/70">
              <span className="text-secondary mr-2">✓</span>
              {feature}
            </li>
          ))}
        </ul>
        
        <button 
          onClick={() => document.getElementById('reservation')?.scrollIntoView({ behavior: 'smooth' })}
          className={`w-full py-3 px-6 rounded-lg font-title font-medium transition-all duration-300 ${
            isPopular
              ? 'bg-accent text-white hover:bg-accent/90'
              : 'bg-secondary text-dark-blue hover:bg-accent'
          }`}
        >
          Reservar
        </button>
      </div>
    </div>
  );
};

const Rooms: React.FC = () => {
  const rooms = [
    {
      title: "La Prisión",
      description: "Despiertas esposado en una celda desconocida. Las paredes están cubiertas de misteriosas inscripciones y el reloj corre en tu contra. ¿Lograrás escapar antes de que sea demasiado tarde?",
      image: imgPrision,
      difficulty: 4,
      players: "2-6 jugadores",
      time: "60 minutos"
    },
    {
      title: "El Misterio del Bosque",
      description: "Adéntrate en un bosque asturiano donde las antiguas leyendas celtas cobran vida. Deberás resolver el secreto ancestral para encontrar el camino de regreso antes del anochecer.",
      image: imgBosque,
      difficulty: 3,
      players: "2-5 jugadores",
      time: "60 minutos"
    }
  ];

  const pricingPlans = [
    {
      title: "Escape para 2 personas",
      price: "30€",
      description: "Experiencia completa en cualquiera de nuestras salas.",
      features: [
        "60 minutos de juego",
        "Atención personalizada",
        "Ambientación temática"
      ]
    },
    {
      title: "Team Building (10 personas)",
      price: "150€",
      description: "Ideal para empresas o grupos grandes que buscan unir lazos y desafiarse juntos.",
      features: [
        "Dinámica adaptada al grupo",
        "Coordinador de sesión",
        "1 hora y media de experiencia",
        "Regalo sorpresa"
      ],
      isPopular: true
    },
    {
      title: "Evento con catering",
      price: "300€",
      description: "Reserva privada del espacio con servicio de catering para celebraciones.",
      features: [
        "Escape personalizado",
        "2 horas de evento",
        "Servicio de comida y bebida",
        "Zona privada para el grupo"
      ]
    }
  ];

  return (
    <section id="rooms" className="py-20 bg-gradient-to-b from-dark-blue to-gray-900">
      <div className="container mx-auto px-4">
        <h2 className="text-3xl md:text-4xl font-title font-extrabold mb-12 text-center">
          <span className="text-secondary">Nuestras</span> Salas
        </h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-20">
          {rooms.map((room, index) => (
            <RoomCard key={index} {...room} />
          ))}
        </div>

        <div className="mt-20">
          <h2 className="text-3xl md:text-4xl font-title font-extrabold mb-4 text-center">
            <span className="text-secondary">Nuestros</span> Precios
          </h2>
          <p className="text-white/70 text-center mb-12 max-w-2xl mx-auto">
            Elige el plan que mejor se adapte a tu grupo y prepárate para vivir una experiencia inolvidable
          </p>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {pricingPlans.map((plan, index) => (
              <PricingCard key={index} {...plan} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};

export default Rooms;