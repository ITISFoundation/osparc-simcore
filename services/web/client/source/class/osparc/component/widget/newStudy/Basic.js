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
 *   let newStudyDlg = new osparc.component.widget.newStudy.Dlg();
 *   this.getRoot().add(newStudyDlg);
 * </pre>
 */

qx.Class.define("osparc.component.widget.newStudy.Basic", {
  extend: qx.ui.core.Widget,

  construct: function(template=null, withPipeline=false) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__createForm(template, withPipeline);
  },

  events: {
    "createStudy": "qx.event.type.Data"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "studyTitle":
          control = new qx.ui.form.TextField().set({
            placeholder: this.tr("Study Title")
          });
          osparc.utils.Utils.setIdToWidget(control, "newStudyTitleFld");
          this.addListener("appear", () => {
            control.activate();
            control.focus();
          });
          this._add(control);
          break;
        case "studyDescription":
          control = new qx.ui.form.TextArea().set({
            minHeight: 150,
            placeholder: this.tr("Describe your study...")
          });
          osparc.utils.Utils.setIdToWidget(control, "newStudyDescFld");
          this._add(control, {
            flex: 1
          });
          break;
        case "studyThumbnail":
          control = new qx.ui.form.TextField().set({
            placeholder: this.tr("URL to the thumbnail")
          });
          osparc.utils.Utils.setIdToWidget(control, "newStudyThumbnailFld");
          this._add(control);
          break;
        case "studyWorkbench":
          control = new qx.ui.form.TextArea().set({
            minHeight: 150,
            placeholder: this.tr("Paste a pipeline here")
          });
          osparc.utils.Utils.setIdToWidget(control, "newStudyWorkbenchFld");
          this._add(control, {
            flex: 1
          });
          break;
        case "createButton":
          control = new qx.ui.form.Button(this.tr("Create"), null, new qx.ui.command.Command("Enter"));
          osparc.utils.Utils.setIdToWidget(control, "newStudySubmitBtn");
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __createForm: function(template, withPipeline) {
      const studyTitle = this.getChildControl("studyTitle").set({
        value: template ? template.name : ""
      });

      const description = this.getChildControl("studyDescription").set({
        value: template ? template.description : ""
      });

      const thumbnail = this.getChildControl("studyThumbnail").set({
        value: template ? template.thumbnail : ""
      });

      let workbench = null;
      if (withPipeline) {
        workbench = this.getChildControl("studyWorkbench");
      }

      if (template) {
        const templateLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
        const label1 = new qx.ui.basic.Label(this.tr("Selected template: "));
        const label2 = new qx.ui.basic.Label(template.name);
        templateLayout.add(label1);
        templateLayout.add(label2);
        this._add(templateLayout);
      }

      const createBtn = this.getChildControl("createButton");

      // create the form manager
      const manager = new qx.ui.form.validation.Manager();
      // create a async validator function
      const studyTitleValidator = new qx.ui.form.validation.AsyncValidator(
        function(validator, value) {
          if (value === null || value.length === 0) {
            studyTitle.setValue("Untitled Study");
          }
          validator.setValid(true);
        }
      );
      manager.add(studyTitle, studyTitleValidator);

      manager.addListener("complete", function() {
        if (!manager.getValid()) {
          return;
        }
        const title = studyTitle.getValue();
        const desc = description.getValue();
        const thumb = thumbnail.getValue();
        const wb = workbench ? workbench.getValue() : null;
        const data = {
          prjTitle: title,
          prjDescription: desc ? desc : "",
          prjThumbnail: thumb ? thumb : "",
          prjWorkbench: wb ? JSON.parse(wb) : {}
        };
        this.fireDataEvent("createStudy", data);
      }, this);

      createBtn.addListener("execute", function() {
        manager.validate();
      }, this);
    }
  }
});
