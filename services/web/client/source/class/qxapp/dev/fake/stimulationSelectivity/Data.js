qx.Class.define("qxapp.dev.fake.stimulationSelectivity.Data", {
  type: "static",

  statics: {
    itemList: [{
      key: "StSeSubgroup-UUID",
      label: "Subgroup"
    }],

    getItemList: function() {
      return qxapp.dev.fake.stimulationSelectivity.Data.itemList;
    }
  } // statics

});
