/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* global window */
/* global document */
/* global XMLHttpRequest */
/* global Blob */

qx.Class.define("qxapp.utils.Utils", {
  type: "static",

  statics: {
    uuidv4: function() {
      return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
        (c ^ window.crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16));
    },

    getLoaderUri: function(arg) {
      let loadingUri = qx.util.ResourceManager.getInstance().toUri("qxapp/loading/loader.html");
      if (arg) {
        loadingUri += "?loading=- ";
        loadingUri += arg;
      }
      return loadingUri;
    },

    createLoadingIFrame: function(text) {
      const loadingUri = qxapp.utils.Utils.getLoaderUri(text);
      let iframe = new qx.ui.embed.Iframe(loadingUri);
      iframe.setBackgroundColor("transparent");
      return iframe;
    },

    compareVersionNumbers: function(v1, v2) {
      // https://stackoverflow.com/questions/6832596/how-to-compare-software-version-number-using-js-only-number/47500834
      let v1parts = v1.split(".");
      let v2parts = v2.split(".");

      for (let i = 0; i < v1parts.length; ++i) {
        if (v2parts.length === i) {
          return 1;
        }
        if (v1parts[i] === v2parts[i]) {
          continue;
        }
        if (v1parts[i] > v2parts[i]) {
          return 1;
        }
        return -1;
      }

      if (v1parts.length != v2parts.length) {
        return -1;
      }

      return 0;
    },

    // deep clone of nested objects
    // https://medium.com/@tkssharma/objects-in-javascript-object-assign-deep-copy-64106c9aefab#eeed
    deepCloneObject: function(src) {
      let target = {};
      for (let key in src) {
        if (src[key] !== null && typeof (src[key]) === "object") {
          target[key] = qxapp.utils.Utils.deepCloneObject(src[key]);
        } else {
          target[key] = src[key];
        }
      }
      return target;
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
    },

    bytesToSize: function(bytes) {
      const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
      if (bytes == 0) {
        return "0 Byte";
      }
      const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)));
      return Math.round(bytes / Math.pow(1024, i), 2) + " " + sizes[i];
    },

    downloadLink: function(url, fileName) {
      let xhr = new XMLHttpRequest();
      xhr.open("GET", url, true);
      xhr.responseType = "blob";
      xhr.onload = () => {
        console.log("onload", xhr);
        if (xhr.status == 200) {
          let blob = new Blob([xhr.response]);
          let urlBlob = window.URL.createObjectURL(blob);
          let downloadAnchorNode = document.createElement("a");
          downloadAnchorNode.setAttribute("href", urlBlob);
          downloadAnchorNode.setAttribute("download", fileName);
          downloadAnchorNode.click();
          downloadAnchorNode.remove();
        }
      };
      xhr.send();
    }
  }
});
