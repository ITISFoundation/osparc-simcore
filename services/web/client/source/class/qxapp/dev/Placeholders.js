/* eslint new-cap: [2, {capIsNewExceptions: ["B", "D", "J", "K", "L", "MD5"]}] */
/* eslint operator-assignment: ["off"] */

qx.Class.define("qxapp.dev.Placeholders", {
  type: "static",

  statics: {

    /**
     * Returns URL to an icon in collection
     *
     * See https://imgplaceholder.com/
    */
    getIcon: function(iconId, width, height = null) {
      // see https://imgplaceholder.com/
      height = (height === null) ? width : height;

      const prefix = "https://imgplaceholder.com/";
      const shape = width + "x" + height;
      const url = prefix + shape + "/transparent/757575/" + iconId;

      // e.g. // https://imgplaceholder.com/128x128/transparent/757575/fa-user
      return url;
    },

    /**
     * Returns URL to a rectangular place-holder image of given
     * dimensions.
     *
     * See https://placeholder.com/
    */
    getImage: function(width, height = null) {
      //

      height = (height === null) ? width : height;
      const url = "//via.placeholder.com/" + width + "x" + height;

      // e.g. http://via.placeholder.com/350x150
      return url;
    }
  }
});
