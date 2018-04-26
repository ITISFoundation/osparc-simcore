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

      var button1 = new qx.ui.form.Button("Temp1");
      button1.set({
        maxWidth: 100,
        minWidth: 100,
        maxHeight: 100,
        alignY:"middle"
      });
      comp.add(button1);
      let scope = this;
      button1.addListener("execute", function() {
        scope.fireDataEvent("StartPrj", "Temp1");
      }, scope);

      var button2 = new qx.ui.form.Button("Temp2");
      button2.set({
        maxWidth: 100,
        minWidth: 100,
        maxHeight: 100,
        alignY:"middle"
      });
      comp.add(button2);
      button2.addListener("execute", function() {
        scope.fireDataEvent("StartPrj", "Temp2");
      }, scope);

      return comp;
    },

    _getPrjUserList: function() {
      let comp = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
      comp.set({
        backgroundColor: "black",
        padding: 10
      });

      var button1 = new qx.ui.form.Button("User1");
      button1.set({
        maxWidth: 100,
        minWidth: 100,
        maxHeight: 100,
        alignY:"middle"
      });
      comp.add(button1);
      let scope = this;
      button1.addListener("execute", function() {
        scope.fireDataEvent("StartPrj", "User1");
      }, scope);

      var button2 = new qx.ui.form.Button("User2");
      button2.set({
        maxWidth: 100,
        minWidth: 100,
        maxHeight: 100,
        alignY:"middle"
      });
      comp.add(button2);
      button2.addListener("execute", function() {
        scope.fireDataEvent("StartPrj", "User2");
      }, scope);

      return comp;
    },

    _getPrjInfoViewer: function() {
      let comp = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      comp.set({
        backgroundColor: "purple",
        padding: 10
      });
      return comp;
    }
  }
});
