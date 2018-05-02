qx.Class.define("qxapp.components.UserMenu", {
  extend: qx.ui.container.Composite,

  include : [qx.locale.MTranslation],

  construct : function(model, backgroundColor, fontColor) {
    this.base(arguments);

    this._model = model;

    this.setLayout(new qx.ui.layout.HBox(0));

    this.add(new qx.ui.basic.Label(this.tr("Hello, ")).set({
      backgroundColor : backgroundColor,
      textColor: fontColor,
      padding : 6,
      allowGrowY: false
    }));

    this._userLabel = new qx.ui.basic.Label(this._getActiveUserName()).set({
      backgroundColor : backgroundColor,
      textColor: fontColor,
      padding : 6,
      allowGrowY: false
    });
    this.add(this._userLabel);


    this._model.addListener("changeActiveUser", function(e) {
      this._userLabel.setValue(this._getActiveUserName());
    }, this);
  },

  members: {
    _model: null,
    _userLabel: null,

    _getActiveUserName : function() {
      const activeUserId = this._model.getActiveUser();
      return this._model.getUsers().toArray()[activeUserId].getName();
    }
  }
});
