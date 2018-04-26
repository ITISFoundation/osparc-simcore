qx.Class.define("qxapp.layout.PrjBrowser", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base();

    this.set({
      layout: new qx.ui.layout.VBox()
    });

    this._PrjTemplateList = this._getPrjTemplateList();
    this._PrjTemplateList.setHeight(200);
    this.add(this._PrjTemplateList);

    this._PrjUserList = this._getPrjUserList();
    this.add(this._PrjUserList, {
      flex: 1
    });

    this._PrjInfoViewer = this._getPrjInfoViewer();
    this._PrjInfoViewer.setHeight(300);
    this.add(this._PrjInfoViewer);
  },

  events: {
    "StartPrj": "qx.event.type.Data"
  },

  members: {
    _PrjTemplateList: null,
    _PrjUserList: null,
    _PrjInfoViewer: null,

    _getPrjTemplateList: function() {
      let comp = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
      comp.set({
        backgroundColor: "red",
        padding: 10
      });

      let tempPrjs = ["Temp1", "Temp2"];
      for (let i = 0; i < tempPrjs.length; i++) {
        let button = this._createStartPrjBtn(tempPrjs[i]);
        comp.add(button);
      }

      return comp;
    },

    _getPrjUserList: function() {
      let comp = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
      comp.set({
        backgroundColor: "black",
        padding: 10
      });

      let userPrjs = ["User1", "User2"];
      for (let i = 0; i < userPrjs.length; i++) {
        let button = this._createStartPrjBtn(userPrjs[i]);
        comp.add(button);
      }

      return comp;
    },

    _getPrjInfoViewer: function() {
      let comp = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      comp.set({
        backgroundColor: "purple",
        padding: 10
      });
      return comp;
    },

    _createStartPrjBtn: function(info) {
      let button = new qx.ui.form.Button(info);
      button.set({
        maxWidth: 100,
        minWidth: 100,
        maxHeight: 100,
        alignY:"middle"
      });

      let scope = this;
      button.addListener("execute", function() {
        scope.fireDataEvent("StartPrj", info);
      }, scope);

      return button;
    }
  }
});
