/**
 * bg.js — Animated sine-wave background, inspired by Basecom design.
 *
 * - Reads --accent-rgb and --wave-opacity from CSS custom properties,
 *   so the theme is controlled entirely from theme.css.
 * - Uses mix-blend-mode: screen (set in theme.css) so the dark canvas
 *   background is invisible and only the wave lines glow through.
 * - Works on every page that includes this script and theme.css.
 */
(function () {
  'use strict';

  var canvas = document.getElementById('bg-canvas');
  if (!canvas) return;

  var ctx = canvas.getContext('2d');
  var W = 0, H = 0, raf = null, t = 0;

  /* Wave layer definitions:
     [amplitudeFactor, spatialFrequency, speed (rad/frame), phaseOffset, yFraction] */
  var WAVES = [
    [0.055, 1.0, 0.012, 0.00, 0.58],
    [0.045, 0.7, 0.009, 2.10, 0.63],
    [0.070, 1.3, 0.015, 1.00, 0.68],
    [0.035, 0.5, 0.007, 4.20, 0.73],
    [0.050, 0.9, 0.011, 3.50, 0.47],
    [0.060, 1.5, 0.016, 5.70, 0.52],
    [0.040, 0.4, 0.008, 1.80, 0.78],
    [0.030, 1.8, 0.018, 0.50, 0.42],
    [0.050, 1.1, 0.013, 2.80, 0.57],
    [0.035, 0.6, 0.010, 6.10, 0.65],
  ];

  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);

    var rgb = cssVar('--accent-rgb') || '108, 99, 255';
    var op  = parseFloat(cssVar('--wave-opacity') || '0.45');

    t++;

    for (var i = 0; i < WAVES.length; i++) {
      var w      = WAVES[i];
      var amp    = H * w[0];
      var freq   = w[1];
      var speed  = w[2];
      var phase  = w[3];
      var baseY  = H * w[4];

      ctx.beginPath();
      for (var x = 0; x <= W; x += 4) {
        var y = baseY + amp * Math.sin(
          freq * (x / W) * Math.PI * 4 + phase + t * speed
        );
        if (x === 0) ctx.moveTo(x, y);
        else         ctx.lineTo(x, y);
      }

      /* Vary line width per layer for depth */
      ctx.lineWidth   = (i % 3 === 0) ? 1.8 : (i % 3 === 1) ? 1.2 : 0.9;
      ctx.strokeStyle = 'rgba(' + rgb + ',' + op + ')';
      ctx.stroke();
    }

    raf = requestAnimationFrame(draw);
  }

  resize();
  window.addEventListener('resize', resize);
  draw();

  window.addEventListener('beforeunload', function () {
    if (raf) cancelAnimationFrame(raf);
  });
}());
