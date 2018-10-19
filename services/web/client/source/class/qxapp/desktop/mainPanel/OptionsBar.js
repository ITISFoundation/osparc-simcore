qx.Class.define("qxapp.desktop.mainPanel.OptionsBar", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__initDefault();
  },

  members: {
    __initDefault: function() {
      let treeBtn = new qx.ui.form.Button();
      treeBtn.setIcon("@FontAwesome5Solid/bars/32");
      this._add(treeBtn);

      let addBtn = new qx.ui.form.Button();
      addBtn.setIcon("@FontAwesome5Solid/plus/32");
      this._add(addBtn);

      let databaseBtn = new qx.ui.form.Button();
      databaseBtn.setIcon("@FontAwesome5Solid/database/32");
      this._add(databaseBtn);

      let linkBtn = new qx.ui.form.Button();
      linkBtn.setIcon("@FontAwesome5Solid/magnet/32");
      this._add(linkBtn);

      let uploadBtn = new qx.ui.form.Button();
      uploadBtn.setIcon("@FontAwesome5Solid/cloud-upload-alt/32");
      this._add(uploadBtn);

      let shareBtn = new qx.ui.form.Button();
      shareBtn.setIcon("@FontAwesome5Solid/share-alt/32");
      this._add(shareBtn);
    }
  }
});
