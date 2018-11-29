/* eslint-disable no-trailing-spaces */
qx.Class.define("qxapp.dev.fake.neuroman.Data", {
  type: "static",

  statics: {
    itemList: [
      {
        key: "Yoon-sun-UUID",
        label: "DemoDec_Neuroman.smash",
        thumbnail: "qxapp/yoonsun.png"
      }, {
        key: "Yoon-sun-Light-UUID",
        label: "DemoDec_OnlyHead_Clean_Modeler.smash",
        thumbnail: "qxapp/yoonsun-light.png"
      }, {
        key: "Rat-UUID",
        label: "DemoDec_OnlyHead_Clean_LF.smash",
        thumbnail: "qxapp/rat.png"
      }, {
        key: "Rat-Light-UUID",
        label: "DemoDec_OnlyHead_Clean_Neuron.smash",
        thumbnail: "qxapp/rat-light.png"
      }, {
        key: "Rat2-UUID",
        label: "ratmodel_simplified.smash",
        thumbnail: "qxapp/rat-light.png"
      }
    ],

    compare: function(a, b) {
      if (a.label < b.label) {
        return -1;
      }
      if (a.label > b.label) {
        return 1;
      }
      return 0;
    },

    getItemList: function() {
      let itemList = qxapp.dev.fake.neuroman.Data.itemList;
      itemList.sort(this.compare);
      return itemList;
    }
  } // statics

});
