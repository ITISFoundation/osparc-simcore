/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that provides the form for creating a new study for a given token
 *
 * After doing some token validation the following data event is fired:
 * <pre class='javascript'>
 *   {
 *     studyId: studyId
 *   };
 * </pre>
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let newStudyWithToken = new osparc.component.widget.newStudy.WithToken();
 *   this.getRoot().add(newStudyWithToken);
 * </pre>
 */

qx.Class.define("osparc.component.widget.newStudy.WithToken", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__createForm();
  },

  events: {
    "autoloadStudy": "qx.event.type.Data"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "studyToken":
          control = new qx.ui.form.TextField().set({
            placeholder: this.tr("Token")
          });
          osparc.utils.Utils.setIdToWidget(control, "newStudyTokenFld");
          this.addListener("appear", () => {
            control.activate();
            control.focus();
          });
          this._add(control);
          break;
        case "createButton":
          control = new qx.ui.form.Button(this.tr("Create"), null, new qx.ui.command.Command("Enter"));
          osparc.utils.Utils.setIdToWidget(control, "newStudySubmitBtn");
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __createForm: function() {
      const token = this.getChildControl("studyToken");
      const createBtn = this.getChildControl("createButton");

      // create the form manager
      const manager = new qx.ui.form.validation.Manager();
      // create a async validator function
      const studyTitleValidator = new qx.ui.form.validation.AsyncValidator(
        function(validator, value) {
          if (value === null || value.length === 0) {
            validator.setValid(false);
          } else {
            validator.setValid(true);
          }
        }
      );
      manager.add(token, studyTitleValidator);

      manager.addListener("complete", function() {
        if (!manager.getValid()) {
          return;
        }
        createBtn.setIcon("@FontAwesome5Solid/circle-notch/12");
        createBtn.getChildControl("icon").getContentElement()
          .addClass("rotate");
        const params = {
          url: {
            "token_id": token.getValue()
          }
        };
        osparc.data.Resources.getOne("sharedStudy", params)
          .then(studyId => {
            createBtn.resetIcon();
            createBtn.getChildControl("icon").getContentElement()
              .removeClass("rotate");
            this.fireDataEvent("autoloadStudy", studyId);
          })
          .catch(err => {
            createBtn.resetIcon();
            console.error(err);
          });
      }, this);

      createBtn.addListener("execute", function() {
        manager.validate();
      }, this);
    }
  }
});
