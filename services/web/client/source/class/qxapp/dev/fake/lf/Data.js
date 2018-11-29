/* eslint-disable no-trailing-spaces */
qx.Class.define("qxapp.dev.fake.lf.Data", {
  type: "static",

  statics: {
    itemList: [
    ],

    getItemList: function() {
      let itemList = qxapp.dev.fake.lf.Data.itemList;
      itemList.sort(this.compare);
      return itemList;
    }
  } // statics

});
