/* global window */

qx.Class.define("qxapp.utils.Utils", {
  type: "static",

  statics:
  {
    uuidv4: function() {
      return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
        (c ^ window.crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16));
    },

    getRandomColor: function() {
      let letters = "0123456789ABCDEF";
      let color = "#";
      for (let i = 0; i < 6; i++) {
        color += letters[Math.floor(Math.random() * 16)];
      }
      return color;
    },

    getColorLuminance: function(hexColor) {
      const rgb = qx.util.ColorUtil.hexStringToRgb(hexColor);
      const luminance = 0.2126*(rgb[0]/255) + 0.7152*(rgb[1]/255) + 0.0722*(rgb[2]/255);
      return luminance;
    },

    hexToRgb: function(hex) {
      // Expand shorthand form (e.g. "03F") to full form (e.g. "0033FF")
      let shorthandRegex = /^#?([a-f\d])([a-f\d])([a-f\d])$/i;
      hex = hex.replace(shorthandRegex, function(m, r, g, b) {
        return r + r + g + g + b + b;
      });

      let result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
      return result ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16)
      } : null;
    },

    inHouse: function(password) {
      if (password === "itis") {
        return true;
      }
      return false;
    },

    getKeyByValue(object, value) {
      return Object.keys(object).find(key => object[key] === value);
    },

    formatBytes: function(bytes) {
      const precision = 2;
      if (bytes < 1024) {
        return bytes + " B";
      } else if (bytes < (1024*1024)) {
        return (bytes / 1024).toFixed(precision) + " KB";
      } else if (bytes < (1024*1024*1024)) {
        return (bytes / (1024*1024)).toFixed(precision) + " MB";
      }
      return (bytes / (1024*1024*1024)).toFixed(precision) + " GB";
    }
  }
});
