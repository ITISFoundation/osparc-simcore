qx.Class.define("qxapp.dev.fake.neuron.Data", {
  type: "static",

  statics: {
    itemList: "asdf",

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
      let itemList = qxapp.dev.fake.neuron.Data.itemList;
      itemList.sort(this.compare);
      return itemList;
    }
  } // statics

});
