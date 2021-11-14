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
 * @asset(radialMenu/RadialMenuES5.js)
 * @ignore(RadialMenu)
 */

/**
 * A qooxdoo wrapper for
 * <a href='https://github.com/victorqribeiro/radialMenu' target='_blank'>RadialMenu</a>
 */

qx.Class.define("osparc.wrapper.RadialMenu", {
  extend: qx.core.Object,
  type: "singleton",

  statics: {
    NAME: "RadialMenu",
    VERSION: "1.2.0",
    URL: "https://github.com/victorqribeiro/radialMenu",

    getButtons: function() {
      return [{
        "text": "\uf053", // plus
        "action": () => {
          console.log("add");
        }
      }, {
        "text": "\uf00e", // search-plus
        "action": () => {
          console.log("in");
        }
      }, {
        "text": "\uf010", // search-minus
        "action": () => {
          console.log("out");
        }
      }];
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
        const radialMenuPath = "radialMenu/RadialMenuES5.js";
        const dynLoader = new qx.util.DynamicScriptLoader([
          radialMenuPath
        ]);

        dynLoader.addListenerOnce("ready", e => {
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
        fontSize: 14,
        textColor: qx.theme.manager.Color.getInstance().resolve("text"),
        backgroundColor: qx.theme.manager.Color.getInstance().resolve("background-main-lighter+"),
        hoverBackgroundColor: qx.theme.manager.Color.getInstance().resolve("contrasted-background+"),
        borderColor: "transparent",
        innerCircle: 20,
        outerCircle: 60,
        rotation: Math.PI / 2, // radians
        buttonGap: 0.01 // radians
        // isFixed: true // we will handle the events
      };
    }
  }
});
