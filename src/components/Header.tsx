import React, { useState, useEffect } from 'react';
import { Menu, X } from 'lucide-react';
import Logo from './Logo';

const Header: React.FC = () => {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      const isScrolled = window.scrollY > 10;
      if (isScrolled !== scrolled) {
        setScrolled(isScrolled);
      }
    };

    document.addEventListener('scroll', handleScroll);
    return () => {
      document.removeEventListener('scroll', handleScroll);
    };
  }, [scrolled]);

  const scrollToSection = (id: string) => {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
      setMenuOpen(false);
    }
  };

  return (
    <header 
      className={`fixed w-full z-50 transition-all duration-300 ${
        scrolled ? 'bg-dark-blue shadow-lg py-2' : 'bg-transparent py-4'
      }`}
    >
      <div className="container mx-auto px-4 flex justify-between items-center">
        <button onClick={() => scrollToSection('home')} className="flex items-center">
          <Logo />
        </button>

        {/* Desktop Menu */}
        <nav className="hidden md:block">
          <ul className="flex space-x-8">
            {['home', 'about', 'partners', 'rooms', 'reservation'].map((item) => (
              <li key={item}>
                <button
                  onClick={() => scrollToSection(item)}
                  className="text-white hover:text-secondary transition-colors font-medium uppercase tracking-wide text-sm"
                >
                  {item === 'home' ? 'Inicio' : 
                   item === 'about' ? 'Sobre Nosotros' :
                   item === 'partners' ? 'Nuestros Socios' :
                   item === 'rooms' ? 'Salas' : 'Reservas'}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        {/* Mobile Menu Button */}
        <button
          className="md:hidden text-white"
          onClick={() => setMenuOpen(!menuOpen)}
        >
          {menuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* Mobile Menu */}
      {menuOpen && (
        <div className="md:hidden bg-dark-blue shadow-lg">
          <ul className="flex flex-col items-center py-4">
            {['home', 'about', 'partners', 'rooms', 'reservation'].map((item) => (
              <li key={item} className="py-2">
                <button
                  onClick={() => scrollToSection(item)}
                  className="text-white hover:text-secondary transition-colors font-medium uppercase tracking-wide text-sm"
                >
                  {item === 'home' ? 'Inicio' : 
                   item === 'about' ? 'Sobre Nosotros' :
                   item === 'partners' ? 'Nuestros Socios' :
                   item === 'rooms' ? 'Salas' : 'Reservas'}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </header>
  );
};

export default Header;