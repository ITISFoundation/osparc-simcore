/**
 * This is a basic Auth-Page with common functionality
 *
 *  - Fixed-size widget with header (title/logo), body and footer (buttons)
 *  - Positioned at the upper center of the root document's window
 */
qx.Class.define("qxapp.auth.core.BaseAuthPage", {
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
      width: 300,
      height: 250
    });

    this._buildPage();
  },

  /*
  *****************************************************************************
     EVENTS
  *****************************************************************************
  */

  events:{
    "done": "qx.event.type.Data"
  },

  /*
  *****************************************************************************
     MEMBERS
  *****************************************************************************
  */

  members: {

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
        // FIXME: should check issubclass of AbstractField
        if (qx.Class.implementsInterface(item, qx.ui.form.IForm) && qx.Class.implementsInterface(item, qx.ui.form.IField)) {
          item.resetValue();
        }
      });
    },

    /**
     * Creates and adds an underlined title at the header
     */
    _addTitleHeader: function(txt) {
      let lbl = new qx.ui.basic.Label(txt).set({
        font: "headline",
        alignX: "center"
      });
      this.add(lbl, {
        flex:1
      });
    }
  }
});
