qx.Class.define("osparc.dev.fake.neuroman.Data", {
  type: "static",

  statics: {
    itemList: {
      "defaultNeuromanModels": [{
        key: "Model-Neuroman-UUID",
        label: "DemoDec_Neuroman.smash",
        thumbnail: "osparc/img1.jpg"
      }, {
        key: "Model-Head-Neuroman-UUID",
        label: "DemoDec_Head_Neuroman.smash",
        thumbnail: "osparc/img2.jpg"
      }, {
        key: "Model-Head-Modeler-UUID",
        label: "DemoDec_Head_Modeler.smash",
        thumbnail: "osparc/img3.jpg"
      }, {
        key: "Model-Head-LF-UUID",
        label: "DemoDec_Head_LF.smash",
        thumbnail: "osparc/img4.jpg"
      }, {
        key: "Model-Head-Neuron-UUID",
        label: "DemoDec_Head_Neuron.smash",
        thumbnail: "osparc/img5.jpg"
      }, {
        key: "Rat-Light-UUID",
        label: "ratmodel_simplified.smash",
        thumbnail: "osparc/img6.jpg"
      }]
    },

    compare: function(a, b) {
      if (a.label < b.label) {
        return -1;
      }
      if (a.label > b.label) {
        return 1;
      }
      return 0;
    },

    getItemList: function(key) {
      let itemList = osparc.dev.fake.neuroman.Data.itemList[key];
      itemList.sort(this.compare);
      return itemList;
    }
  } // statics

});
