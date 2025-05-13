/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        'dark-blue': '#0A3B5C',
        'secondary': '#FFC700',
        'accent': '#FF8200',
        'dark-gray': '#222222',
      },
      fontFamily: {
        title: ['Montserrat', 'sans-serif'],
        body: ['Roboto', 'sans-serif'],
      },
      animation: {
        bounce: 'bounce 1s infinite',
      },
      keyframes: {
        bounce: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
      },
      spacing: {
        'logo': '6rem',     // 64px (móvil)
        'logo-md': '3rem',  // 96px (tablet)
        'logo-lg': '10rem',  // 128px (escritorio)
      }
    },
  },
  plugins: [],
};