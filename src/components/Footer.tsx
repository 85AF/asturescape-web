import React from 'react';
import { Facebook, Instagram, Twitter, Mail, MapPin, Phone } from 'lucide-react';
import Logo from './Logo';

const Footer: React.FC = () => {
  const currentYear = new Date().getFullYear();
  
  return (
    <footer className="bg-dark-blue py-12 border-t border-gray-800">
      <div className="container mx-auto px-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-10">
          <div>
            <Logo className="mb-4" />
            <p className="text-white/70 mb-4">
              Ofrecemos experiencias de escape room únicas inspiradas en las leyendas y misterios de Asturias.
            </p>
            <div className="flex space-x-4">
              <a href="#" className="text-white/70 hover:text-secondary transition-colors">
                <Facebook size={20} />
              </a>
              <a href="#" className="text-white/70 hover:text-secondary transition-colors">
                <Instagram size={20} />
              </a>
              <a href="#" className="text-white/70 hover:text-secondary transition-colors">
                <Twitter size={20} />
              </a>
            </div>
          </div>
          
          <div>
            <h3 className="text-xl font-title font-bold mb-4 text-white">Contacto</h3>
            <ul className="space-y-3 text-white/70">
              <li className="flex items-start">
                <MapPin size={18} className="mr-2 mt-1 flex-shrink-0" />
                <span>Calle Principal 123, Avilés, Asturias</span>
              </li>
              <li className="flex items-center">
                <Phone size={18} className="mr-2 flex-shrink-0" />
                <span>+34 984 123 456</span>
              </li>
              <li className="flex items-center">
                <Mail size={18} className="mr-2 flex-shrink-0" />
                <span>info@asturescape.com</span>
              </li>
            </ul>
          </div>
          
          <div>
            <h3 className="text-xl font-title font-bold mb-4 text-white">Horario</h3>
            <ul className="space-y-2 text-white/70">
              <li className="flex justify-between">
                <span>Lunes - Viernes:</span>
                <span>16:00 - 22:00</span>
              </li>
              <li className="flex justify-between">
                <span>Sábado:</span>
                <span>11:00 - 23:00</span>
              </li>
              <li className="flex justify-between">
                <span>Domingo:</span>
                <span>11:00 - 21:00</span>
              </li>
            </ul>
          </div>
        </div>
        
        <div className="border-t border-gray-800 mt-10 pt-6 text-center text-white/50 text-sm">
          <p>&copy; {currentYear} AsturEscape. Todos los derechos reservados.</p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;