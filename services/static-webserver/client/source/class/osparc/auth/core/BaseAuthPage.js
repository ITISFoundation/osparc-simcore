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
 *  - Fixed-size widget with header (title/logo), body and footer (buttons)
 *  - Positioned at the upper center of the root document's window
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

    // TODO: remove fix dimensions for the outer container?
    this.set({
      layout: new qx.ui.layout.VBox(20),
      width: this.self().FORM_WIDTH,
      height: 300
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
    FORM_WIDTH: 300
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
    /**
     * This method gets called upon construction and
     * must be overriden in a subclass
     *
     * @signature function()
     */
    _buildPage: null,

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
      const lbl = new qx.ui.basic.Label(txt).set({
        font: "text-18",
        alignX: "center"
      });
      this.add(lbl, {
        flex:1
      });
    },

    _onAppear: function() {
      return;
    },

    _onDisappear: function() {
      return;
    }
  }
});
