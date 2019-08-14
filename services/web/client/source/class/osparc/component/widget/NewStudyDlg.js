/* ************************************************************************

   osparc - the simcore frontend

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
 *     prjTemplateId: templ
 *   };
 * </pre>
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let newStudyDlg = new osparc.component.widget.NewStudyDlg();
 *   this.getRoot().add(newStudyDlg);
 * </pre>
 */

qx.Class.define("osparc.component.widget.NewStudyDlg", {
  extend: qx.ui.core.Widget,

  construct: function(template=null) {
    this.base(arguments);

    let newPrjLayout = new qx.ui.layout.Canvas();
    this._setLayout(newPrjLayout);

    this.__createForm(template);
  },

  events: {
    "createStudy": "qx.event.type.Data"
  },

  members: {
    __createForm: function(template) {
      const prjFormLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const studyTitle = new qx.ui.form.TextField().set({
        placeholder: this.tr("Study Title"),
        value: template ? template.name : ""
      });
      this.addListener("appear", () => {
        studyTitle.activate();
        studyTitle.focus();
      });
      prjFormLayout.add(studyTitle);

      const description = new qx.ui.form.TextArea().set({
        minHeight: 150,
        placeholder: this.tr("Describe your study..."),
        value: template ? template.description : ""
      });
      prjFormLayout.add(description, {
        flex: 1
      });

      if (template) {
        const templateLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
        const label1 = new qx.ui.basic.Label(this.tr("Selected template: "));
        const label2 = new qx.ui.basic.Label(template.name);
        templateLayout.add(label1);
        templateLayout.add(label2);
        prjFormLayout.add(templateLayout);
      }

      const createBtn = new qx.ui.form.Button(this.tr("Create"));
      prjFormLayout.add(createBtn);

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
        const data = {
          prjTitle: title,
          prjDescription: desc ? desc : ""
        };
        if (template) {
          data["prjTemplateId"] = template.uuid;
        }
        this.fireDataEvent("createStudy", data);
      }, this);

      createBtn.addListener("execute", function() {
        manager.validate();
      }, this);

      this._add(prjFormLayout, {
        top: 10,
        right: 10,
        bottom: 10,
        left: 10
      });
    }
  }
});
