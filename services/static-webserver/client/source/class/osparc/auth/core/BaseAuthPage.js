/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)

************************************************************************ */

/**
 * This is a basic Auth-Page with common functionality
 *
 *  - Widget with title, form and buttons
 */
qx.Class.define("osparc.auth.core.BaseAuthPage", {
  extend: qx.ui.container.Composite,
  type: "abstract",

  /*
  *****************************************************************************
     CONSTRUCTOR
  *****************************************************************************
  */

  construct: function() {
    this.base(arguments);

    this.set({
      layout: new qx.ui.layout.VBox(20),
      width: this.self().FORM_WIDTH
    });

    this._form = new qx.ui.form.Form();
    this._buildPage();

    this.addListener("appear", this._onAppear, this);
    this.addListener("disappear", this._onDisappear, this);
  },

  /*
  *****************************************************************************
     EVENTS
  *****************************************************************************
  */

  events:{
    "done": "qx.event.type.Data"
  },

  statics: {
    FORM_WIDTH: 310
  },

  /*
  *****************************************************************************
     MEMBERS
  *****************************************************************************
  */

  members: {
    /**
     * when all is said and done we should remove the form so that the password manager
     * knows to save the content of the form. so we save it here.
     */
    _form: null,

    _buildPage: function() {
      throw new Error("Abstract method called!");
    },

    beautifyFormFields: function() {
      const formItems = this._form.getItems();
      Object.keys(formItems).forEach(fieldKey => {
        const formItem = formItems[fieldKey];
        formItem.set({
          width: this.self().FORM_WIDTH,
          appearance: "form-input"
        });
        if (formItem.classname === "osparc.ui.form.PasswordField") {
          formItem.getChildControl("passwordField").set({
            backgroundColor: "transparent",
            appearance: "form-password"
          });
        }
      });
    },

    /**
     * This method needs to be implemented in subclass
     * and should reset all field values
    */
    resetValues: function() {
      this.getChildren().forEach(item => {
        // FIXME: should check is subclass of AbstractField
        if (qx.Class.implementsInterface(item, qx.ui.form.IForm) && qx.Class.implementsInterface(item, qx.ui.form.IField)) {
          item.resetValue();
        }
      });
    },

    /**
     * Creates and adds an underlined title at the header
     */
    _addTitleHeader: function(txt) {
      const title = new qx.ui.basic.Label(txt).set({
        font: "text-18",
        alignX: "center"
      });
      this.add(title);
    },

    _onAppear: function() {
      return;
    },

    _onDisappear: function() {
      return;
    }
  }
});
