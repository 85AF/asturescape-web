import React, { useState } from 'react';

interface FormData {
  name: string;
  email: string;
  date: string;
  room: string;
  people: number;
}

const Reservation: React.FC = () => {
  const [formData, setFormData] = useState<FormData>({
    name: '',
    email: '',
    date: '',
    room: '',
    people: 2
  });
  
  const [success, setSuccess] = useState(false);
  
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData({
      ...formData,
      [name]: value
    });
  };
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Here you would typically send the data to your backend
    console.log(formData);
    
    // Show success message
    setSuccess(true);
    
    // Reset form
    setFormData({
      name: '',
      email: '',
      date: '',
      room: '',
      people: 2
    });
    
    // Hide success message after 5 seconds
    setTimeout(() => {
      setSuccess(false);
    }, 5000);
  };

  return (
    <section id="reservation" className="py-20 bg-gradient-to-b from-gray-900 to-dark-blue">
      <div className="container mx-auto px-4">
        <h2 className="text-3xl md:text-4xl font-title font-extrabold mb-12 text-center">
          <span className="text-secondary">Reserva</span> Tu Aventura
        </h2>
        
        <div className="max-w-2xl mx-auto">
          {success && (
            <div className="bg-green-700 text-white p-4 rounded-lg mb-6 animate-fade-in">
              <p className="font-bold">¡Reserva realizada con éxito!</p>
              <p>Te hemos enviado un correo con los detalles de tu reserva.</p>
            </div>
          )}
          
          <div className="bg-dark-gray rounded-lg p-8 shadow-xl">
            <form onSubmit={handleSubmit}>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="col-span-2 md:col-span-1">
                  <label htmlFor="name" className="block text-white mb-2">Nombre completo</label>
                  <input
                    type="text"
                    id="name"
                    name="name"
                    value={formData.name}
                    onChange={handleChange}
                    required
                    className="w-full px-4 py-2 rounded-lg bg-gray-800 text-white border border-gray-700 focus:border-secondary focus:outline-none focus:ring-1 focus:ring-secondary"
                  />
                </div>
                
                <div className="col-span-2 md:col-span-1">
                  <label htmlFor="email" className="block text-white mb-2">Email</label>
                  <input
                    type="email"
                    id="email"
                    name="email"
                    value={formData.email}
                    onChange={handleChange}
                    required
                    className="w-full px-4 py-2 rounded-lg bg-gray-800 text-white border border-gray-700 focus:border-secondary focus:outline-none focus:ring-1 focus:ring-secondary"
                  />
                </div>
                
                <div className="col-span-2 md:col-span-1">
                  <label htmlFor="date" className="block text-white mb-2">Fecha y hora</label>
                  <input
                    type="datetime-local"
                    id="date"
                    name="date"
                    value={formData.date}
                    onChange={handleChange}
                    required
                    className="w-full px-4 py-2 rounded-lg bg-gray-800 text-white border border-gray-700 focus:border-secondary focus:outline-none focus:ring-1 focus:ring-secondary"
                  />
                </div>
                
                <div className="col-span-2 md:col-span-1">
                  <label htmlFor="room" className="block text-white mb-2">Sala</label>
                  <select
                    id="room"
                    name="room"
                    value={formData.room}
                    onChange={handleChange}
                    required
                    className="w-full px-4 py-2 rounded-lg bg-gray-800 text-white border border-gray-700 focus:border-secondary focus:outline-none focus:ring-1 focus:ring-secondary"
                  >
                    <option value="">Selecciona una sala</option>
                    <option value="prision">La Prisión</option>
                    <option value="bosque">El Misterio del Bosque</option>
                  </select>
                </div>
                
                <div className="col-span-2">
                  <label htmlFor="people" className="block text-white mb-2">Número de personas</label>
                  <input
                    type="number"
                    id="people"
                    name="people"
                    min="2"
                    max="6"
                    value={formData.people}
                    onChange={handleChange}
                    required
                    className="w-full px-4 py-2 rounded-lg bg-gray-800 text-white border border-gray-700 focus:border-secondary focus:outline-none focus:ring-1 focus:ring-secondary"
                  />
                </div>
                
                <div className="col-span-2">
                  <div className="flex items-start mb-4">
                    <input
                      id="terms"
                      type="checkbox"
                      required
                      className="h-4 w-4 rounded border-gray-300 text-secondary focus:ring-secondary mt-1"
                    />
                    <label htmlFor="terms" className="ml-2 block text-sm text-white/80">
                      Acepto los términos y condiciones y la política de privacidad
                    </label>
                  </div>
                </div>
                
                <div className="col-span-2">
                  <button
                    type="submit"
                    className="w-full bg-secondary hover:bg-accent text-dark-blue font-bold py-3 px-4 rounded-lg transition-colors duration-300"
                  >
                    Reservar Ahora
                  </button>
                </div>
              </div>
            </form>
            
            <div className="mt-6 text-center text-sm text-white/60">
              <p>* Las reservas deben realizarse con al menos 24 horas de antelación.</p>
              <p>* Consulta nuestra política de cancelación y promociones para grupos.</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Reservation;