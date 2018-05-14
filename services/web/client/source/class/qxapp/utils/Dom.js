/* global document */

qx.Class.define("qxapp.utils.Dom", {
  type: "static",

  statics: {
    getDocWidth: function() {
      //  Check qx.bom.Document
      let body = document.body;
      let html = document.documentElement;
      let docWidth = Math.max(body.scrollWidth, body.offsetWidth, html.clientWidth, html.scrollWidth, html.offsetWidth);
      return docWidth;
    },

    getDocHeight: function() {
      let body = document.body;
      let html = document.documentElement;
      let docHeight = Math.max(body.scrollHeight, body.offsetHeight, html.clientHeight, html.scrollHeight, html.offsetHeight);
      return docHeight;
    },

    getCenteredLoc: function(width, height) {
      const x0 = qxapp.utils.Dom.getDocWidth()/2;
      const y0 = qxapp.utils.Dom.getDocHeight()/2;
      const left = Math.round(x0 - width / 2);
      const top = Math.round(y0 - height / 2);
      return [left, top];
    }
  }
});
