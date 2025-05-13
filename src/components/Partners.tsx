import React from 'react';
import sophiaImg from '../assets/imagenes/sophia.jpg';
import albertoImg from '../assets/imagenes/alberto.jpg';

interface PartnerProps {
  name: string;
  role: string;
  image: string;
  description: string;
}

const PartnerCard: React.FC<PartnerProps> = ({ name, role, image, description }) => {
  return (
    <div className="bg-dark-gray rounded-lg overflow-hidden shadow-lg transform hover:scale-105 transition-all duration-300">
      <div className="h-64 overflow-hidden">
        <img 
          src={image} 
          alt={name} 
          className="w-full h-full object-cover object-center"
        />
      </div>
      <div className="p-6">
        <h3 className="text-xl font-title font-bold mb-1 text-secondary">{name}</h3>
        <p className="text-sm text-accent mb-4 font-medium">{role}</p>
        <p className="text-white/80">{description}</p>
      </div>
    </div>
  );
};

const Partners: React.FC = () => {
  const partners = [
    {
      name: "Sophia Fernández",
      role: "Directora de Operaciones",
      image: sophiaImg,
      description: "Con experiencia en gestión de eventos, Sophia se asegura de que cada detalle esté perfecto..."
    },
    {
      name: "Alberto Fernández",
      role: "Director Creativo",
      image: albertoImg,
      description: "Apasionado por los acertijos y juegos de escape..."
    }
  ];

  return (
    <section id="partners" className="py-20 bg-gradient-to-b from-gray-900 to-dark-blue">
      <div className="container mx-auto px-4">
        <h2 className="text-3xl md:text-4xl font-title font-extrabold mb-12 text-center">
          <span className="text-secondary">Nuestros</span> Socios
        </h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
          {partners.map((partner, index) => (
            <PartnerCard key={index} {...partner} />
          ))}
        </div>
      </div>
    </section>
  );
};

export default Partners;