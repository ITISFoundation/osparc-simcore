/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that provides the form for creating a new study
 *
 * After doing some Study title validation the following data event is fired:
 * <pre class='javascript'>
 *   {
 *     prjTitle: title,
 *     prjDescription: desc,
 *     prjTemplate: templ
 *   };
 * </pre>
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let newStudyDlg = new qxapp.component.widget.NewStudyDlg();
 *   this.getRoot().add(newStudyDlg);
 * </pre>
 */

qx.Class.define("qxapp.component.widget.NewStudyDlg", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    let newPrjLayout = new qx.ui.layout.Canvas();
    this._setLayout(newPrjLayout);

    this.__createForm();
  },

  events: {
    "createStudy": "qx.event.type.Data"
  },

  members: {
    __createForm: function() {
      const prjFormLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const studyTitle = new qx.ui.form.TextField().set({
        placeholder: this.tr("Study Title")
      });
      this.addListener("appear", () => {
        studyTitle.activate();
        studyTitle.focus();
      });
      prjFormLayout.add(studyTitle);

      prjFormLayout.add(new qx.ui.core.Spacer(5));

      const description = new qx.ui.form.TextArea().set({
        minHeight: 150,
        placeholder: this.tr("Describe your study...")
      });
      prjFormLayout.add(description, {
        flex: 1
      });

      prjFormLayout.add(new qx.ui.core.Spacer(5));

      const templatesList = new qx.ui.form.List().set({
        minHeight: 200
      });
      const blankItem = new qx.ui.form.ListItem(this.tr("Blank Study"));
      templatesList.add(blankItem);
      templatesList.add(new qx.ui.form.ListItem(this.tr("EM General")));
      templatesList.add(new qx.ui.form.ListItem(this.tr("EM-Neuro")));
      templatesList.add(new qx.ui.form.ListItem(this.tr("EM-Thermal")));
      templatesList.setSelection([blankItem]);
      prjFormLayout.add(new qx.ui.basic.Label(this.tr("Categories / Templates")));
      prjFormLayout.add(templatesList, {
        flex: 1
      });

      prjFormLayout.add(new qx.ui.core.Spacer(5));

      // create the form manager
      const manager = new qx.ui.form.validation.Manager();
      // create a async validator function
      const studyTitleValidator = new qx.ui.form.validation.AsyncValidator(
        function(validator, value) {
          if (value === null || value.length === 0) {
            validator.setValid(false, "Study title is required");
          } else {
            validator.setValid(true);
          }
        }
      );
      manager.add(studyTitle, studyTitleValidator);

      manager.addListener("complete", function() {
        if (!manager.getValid()) {
          return;
        }
        const title = studyTitle.getValue();
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
        this.fireDataEvent("createStudy", data);
      }, this);

      const createBtn = new qx.ui.form.Button(this.tr("Create"));
      createBtn.addListener("execute", function() {
        manager.validate();
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
