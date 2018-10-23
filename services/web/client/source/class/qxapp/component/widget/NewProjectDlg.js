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

      let templatesList = new qx.ui.form.List().set({
        minHeight: 200
      });
      templatesList.add(new qx.ui.form.ListItem(this.tr("Blank Project")));
      templatesList.add(new qx.ui.form.ListItem(this.tr("EM General")));
      templatesList.add(new qx.ui.form.ListItem(this.tr("EM-Neuro")));
      templatesList.add(new qx.ui.form.ListItem(this.tr("Antennas")));
      prjFormLayout.add(new qx.ui.basic.Label(this.tr("Categories / Templates")));
      prjFormLayout.add(templatesList, {
        flex: 1
      });

      prjFormLayout.add(new qx.ui.core.Spacer(5));

      let creditCardLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      let planList = new qx.ui.form.List().set({
        height: 50
      });
      planList.add(new qx.ui.form.ListItem(this.tr("Monthly Subscription")));
      planList.add(new qx.ui.form.ListItem(this.tr("Yearly Subscription")));
      creditCardLayout.add(new qx.ui.basic.Label(this.tr("Plan")));
      creditCardLayout.add(planList);

      let ccDataLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      let ccIcon = new qx.ui.basic.Atom().set({
        icon: "@FontAwesome5Solid/credit-card/24"
      });
      let ccNumber = new qx.ui.form.TextField().set({
        placeholder: this.tr("Credit Card Number")
      });
      let expDate = new qx.ui.form.TextField().set({
        placeholder: this.tr("Exp. Date"),
        width: 100
      });
      ccDataLayout.add(ccIcon);
      ccDataLayout.add(ccNumber, {
        flex: 1
      });
      ccDataLayout.add(expDate);
      creditCardLayout.add(ccDataLayout);

      creditCardLayout.setVisibility("excluded");

      let privateCB = new qx.ui.form.CheckBox(this.tr("Private"));
      privateCB.addListener("changeValue", function(e) {
        const showCC = e.getData();
        if (showCC) {
          creditCardLayout.setVisibility("visible");
        } else {
          creditCardLayout.setVisibility("excluded");
        }
      }, this);
      prjFormLayout.add(privateCB);
      prjFormLayout.add(creditCardLayout);

      prjFormLayout.add(new qx.ui.core.Spacer(5));

      let createBtn = new qx.ui.form.Button(this.tr("Create"));
      createBtn.addListener("execute", function() {
        const title = projectTitle.getValue();
        const desc = description.getValue();
        const sele = templatesList.getSelection();
        let templ = "";
        if (sele && sele.length > 0) {
          templ = sele[0].getLabel().getMessageId();
        }
        const data = {
          prjTitle: title,
          prjDescription: desc,
          prjTemplate: templ
        };
        this.fireDataEvent("CreatePrj", data);
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
