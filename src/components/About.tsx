import React from 'react';
import img1 from '../assets/imagenes/1ERooms.jpg';
import img2 from '../assets/imagenes/2ERooms.jpg';
import img3 from '../assets/imagenes/3ERooms.jpg';

const About: React.FC = () => {
  return (
    <section id="about" className="py-20 bg-gradient-to-b from-dark-blue to-gray-900">
      <div className="container mx-auto px-4">
        <h2 className="text-3xl md:text-4xl font-title font-extrabold mb-12 text-center">
          <span className="text-secondary">Sobre</span> Nosotros
        </h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-10 items-center">
          <div className="order-2 md:order-1">
            <h3 className="text-2xl font-title font-bold mb-4 text-white">
              Una experiencia <span className="text-secondary">inmersiva</span>
            </h3>
            
            <p className="mb-6 text-white/80 leading-relaxed">
              AsturEscape nace en 2023 en Avilés como un proyecto innovador que busca 
              ofrecer experiencias únicas y desafiantes. Nuestras salas están diseñadas para 
              sumergirte en historias fascinantes inspiradas en leyendas asturianas, 
              misterios locales y enigmas universales.
            </p>
            
            <p className="mb-6 text-white/80 leading-relaxed">
              Nuestra misión es proporcionar una alternativa de ocio que combine diversión, 
              adrenalina y trabajo en equipo. Creemos en el poder del juego como herramienta 
              para fortalecer lazos entre amigos, familias y compañeros de trabajo.
            </p>
            
            <div className="bg-dark-gray rounded-lg p-4 border-l-4 border-secondary">
              <p className="italic text-white/90">
                "Cada sala es un mundo distinto, cada enigma una nueva historia, 
                cada minuto una batalla contra el tiempo."
              </p>
            </div>
          </div>
          
          <div className="order-1 md:order-2 grid grid-cols-2 gap-4">
            <div className="aspect-square rounded-lg overflow-hidden transform hover:scale-105 transition-transform duration-300">
              <img src={img1} alt="Escape room experience" className="w-full h-full object-cover" />
            </div>
            <div className="aspect-square rounded-lg overflow-hidden transform translate-y-8 hover:scale-105 transition-transform duration-300">
              <img src={img2} alt="Team solving puzzles" className="w-full h-full object-cover" />
            </div>
            <div className="aspect-square rounded-lg overflow-hidden transform translate-y-4 hover:scale-105 transition-transform duration-300 col-span-2">
              <img src={img3} alt="Mystery elements" className="w-full h-full object-cover" />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default About;