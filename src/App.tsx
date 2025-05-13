import React from 'react';
import Header from './components/Header';
import Home from './components/Home';
import About from './components/About';
import Partners from './components/Partners';
import Rooms from './components/Rooms';
import Reservation from './components/Reservation';
import Footer from './components/Footer';

function App() {
  return (
    <div className="font-body text-white bg-dark-blue min-h-screen">
      <Header />
      <main>
        <Home />
        <About />
        <Partners />
        <Rooms />
        <Reservation />
      </main>
      <Footer />
    </div>
  );
}

export default App;