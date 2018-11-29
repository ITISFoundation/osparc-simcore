qx.Class.define("qxapp.dev.fake.stimulationSelectivity.Data", {
  type: "static",

  statics: {
    itemList: [{
      key: "StSeSubgroup-UUID",
      label: "Subgroup"
    }],

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
      let itemList = qxapp.dev.fake.stimulationSelectivity.Data.itemList;
      itemList.sort(this.compare);
      return itemList;
    }
  } // statics

});
