qx.Class.define("qxapp.component.widget.NewProjectDlg", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    let newPrjLayout = new qx.ui.layout.Canvas();
    this._setLayout(newPrjLayout);

    this.__createForm();
  },

  events: {
    "CreatePrj": "qx.event.type.Data"
  },

  members: {
    __createForm: function() {
      let prjFormLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      let projectTitle = new qx.ui.form.TextField().set({
        placeholder: this.tr("Project Title")
      });
      prjFormLayout.add(projectTitle);

      prjFormLayout.add(new qx.ui.core.Spacer(5));

      let description = new qx.ui.form.TextArea().set({
        minHeight: 150,
        placeholder: this.tr("Describe your project...")
      });
      prjFormLayout.add(description, {
        flex: 1
      });

      prjFormLayout.add(new qx.ui.core.Spacer(5));

      let list = new qx.ui.form.List().set({
        minHeight: 200
      });
      list.add(new qx.ui.form.ListItem(this.tr("Blank Project")));
      list.add(new qx.ui.form.ListItem(this.tr("EM General")));
      list.add(new qx.ui.form.ListItem(this.tr("EM-Neuro")));
      list.add(new qx.ui.form.ListItem(this.tr("EM-Thermal")));
      list.add(new qx.ui.form.ListItem(this.tr("Antennas")));
      list.add(new qx.ui.form.ListItem(this.tr("Acoustics")));
      prjFormLayout.add(new qx.ui.basic.Label(this.tr("Categories / Templates")));
      prjFormLayout.add(list, {
        flex: 1
      });

      let createBtn = new qx.ui.form.Button("Create");
      createBtn.addListener("execute", function() {
        console.log("CreatePrj");
      }, this);
      prjFormLayout.add(createBtn);

      this._add(prjFormLayout, {
        top: 10,
        right: 10,
        bottom: 10,
        left: 10
      });
    }
  }
});
