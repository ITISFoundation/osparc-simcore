/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* global RadialMenu */

/**
 * @asset(radialMenu/RadialMenu.js)
 * @ignore(RadialMenu)
 */

/**
 * A qooxdoo wrapper for
 * <a href='https://github.com/victorqribeiro/radialMenu' target='_blank'>RadialMenu</a>
 */

qx.Class.define("osparc.wrapper.RadialMenu", {
  extend: qx.core.Object,

  statics: {
    NAME: "RadialMenu",
    VERSION: "1.2.0",
    URL: "https://github.com/victorqribeiro/radialMenu",

    getButtons: function() {
      return {
        textColor: "red",
        buttons: [{
          "text": "\uf053",
          "action": () => {
            history.go(-1); // create a button that goes back on history
          }
        }, {
          "text": "\uf054",
          "action": () => {
            history.go(1); // create a button tha goes forward on history
          }
        }]
      };
    }
  },

  properties: {
    libReady: {
      nullable: false,
      init: false,
      check: "Boolean"
    }
  },

  members: {
    init: function() {
      return new Promise((resolve, reject) => {
        // initialize the script loading
        const radialMenuPath = "radialMenu/RadialMenu.js";
        const dynLoader = new qx.util.DynamicScriptLoader([
          radialMenuPath
        ]);

        dynLoader.addListenerOnce("ready", e => {
          console.log(radialMenuPath + " loaded");
          this.setLibReady(true);
          resolve(true);
        }, this);

        dynLoader.addListener("failed", e => {
          let data = e.getData();
          console.error("failed to load " + data.script);
          reject(data);
        }, this);

        dynLoader.start();
      });
    },

    createMenu: function() {
      const settings = this.__getSettings();
      const radialMenu = new RadialMenu(settings);
      return radialMenu;
    },

    __getSettings: function() {
      return {
        fontFamily: "Roboto",
        fontSize: 14,
        textColor: "red",
        backgroundColor: "blue",
        hoverBackgroundColor: "green",
        innerCircle: 50,
        outerCircle: 100,
        buttonGap: 0,
        borderColor: "white"
      };
    }
  }
});
