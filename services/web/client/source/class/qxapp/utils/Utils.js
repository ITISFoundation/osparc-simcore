/* global window */

qx.Class.define("qxapp.utils.Utils", {
  type: "static",

  statics:
  {
    uuidv4: function() {
      return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
        (c ^ window.crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16));
    },

    replaceTemplateUUIDs: function(data) {
      const tempPrefix = "template-uuid";
      let myData = JSON.stringify(data);
      let tempIdIdx = myData.indexOf(tempPrefix);
      while (tempIdIdx !== -1) {
        let tempId = myData.substr(tempIdIdx, 36);
        let tempLocIdIdx = myData.indexOf(tempId);
        let newUuid = qxapp.utils.Utils.uuidv4();
        while (tempLocIdIdx !== -1) {
          myData = myData.replace(tempId, newUuid);
          tempLocIdIdx = myData.indexOf(tempId);
        }
        tempIdIdx = myData.indexOf(tempPrefix);
      }
      data = JSON.parse(myData);
      return data;
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

    getKeyByValue(object, value) {
      return Object.keys(object).find(key => object[key] === value);
    }
  }
});
