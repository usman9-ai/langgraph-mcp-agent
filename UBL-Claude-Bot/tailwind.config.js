/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#F7F7F5',
        secondary: '#FFFFFF',
        hover: '#F0EEE9',
        tertiary: '#FAFAF9',
        accent: '#003366',
        'accent-hover': '#8ccbf3',
        border: '#E5E3DE',
        'border-light': '#F0EEE9',
        'text-primary': '#000000',
        'text-secondary': '#404040',
      },
    },
  },
  plugins: [],
}
