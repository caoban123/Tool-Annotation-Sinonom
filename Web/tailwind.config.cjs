module.exports = {
  content: ['./app/templates/**/*.html', './app/static/**/*.js'],
  theme: {extend: {
    colors: {
      brand: {50:'#f0fdf4',500:'#16a34a',600:'#15803d',700:'#166534'},
      han: {50:'#f0f7ff',100:'#e0effe',200:'#bae0fd',500:'#0284c7',600:'#0369a1',700:'#075985',900:'#0c4a6e'},
      viet: {50:'#fff1f2',100:'#ffe4e6',200:'#fecdd3',500:'#e11d48',600:'#be123c',700:'#9f1239',900:'#881337'}},
    fontFamily: {sans:['Inter','system-ui','sans-serif'],cjk:['Noto Serif TC','Microsoft JhengHei','SimSun','serif']},
    boxShadow: {xs:'0 1px 2px rgb(0 0 0 / .05)',subtle:'0 1px 3px rgb(0 0 0 / .05)','card-hover':'0 10px 25px -5px rgb(0 0 0 / .08)'}
  }}, plugins: []
};
