qx.Class.define("qxapp.components.UserMenu", {
  extend: qx.ui.container.Composite,

  include : [qx.locale.MTranslation],

  construct : function(model, backgroundColor, fontColor) {
    this.base(arguments);

    this.__model = model;

    this.setLayout(new qx.ui.layout.HBox(0));

    this.add(new qx.ui.basic.Label(this.tr("Hello, ")).set({
      backgroundColor : backgroundColor,
      textColor: fontColor,
      padding : 6,
      allowGrowY: false
    }));

    this.__userLabel = new qx.ui.basic.Label(this.getActiveUserName()).set({
      backgroundColor : backgroundColor,
      textColor: fontColor,
      padding : 6,
      allowGrowY: false
    });
    this.add(this.__userLabel);


    this.__model.addListener("changeActiveUser", function(e) {
      this.__userLabel.setValue(this.getActiveUserName());
    }, this);
  },

  members: {
    __model: null,
    __userLabel: null,

    getActiveUserName: function() {
      const activeUserId = this.__model.getActiveUser();
      return this.__model.getUsers().toArray()[activeUserId].getName();
    }
  }
});
