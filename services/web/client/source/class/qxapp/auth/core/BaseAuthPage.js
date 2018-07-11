/**
 * This is a basic Auth-Page with common functionality
 *
 *  - Fixed-size widget with header (title/logo), body and footer (buttons)
 *  - Positioned at the upper center of the root document's window
 */
qx.Class.define("qxapp.auth.core.BaseAuthPage", {
  extend: qx.ui.container.Composite,
  include: [
    qxapp.auth.core.MAuth
  ],
  type: "abstract",

  statics: {

    addPageToRoot: function(page) {
      // TODO: should be automatically reposition of document size changed!?

      let top = parseInt((qx.bom.Document.getHeight() - page.getHeight()) / 4, 10);
      let left = parseInt((qx.bom.Document.getWidth() - page.getWidth()) / 2, 10);

      let app = qx.core.Init.getApplication();
      app.getRoot().removeAll();
      app.getRoot().add(page, {
        top: top,
        left: left
      });
    }
  },


  construct: function() {
    this.base(arguments);

    // Setup children's layout and the auth page widget dimensions
    // TODO: remove fix dimensions for the outer container?
    const spacing = 20;
    this.setLayout(new qx.ui.layout.VBox(spacing));
    this.set({
      width: 300,
      height: 250,
      allowGrowX: false,
      allowGrowY: false,
      alignX: "center"
    });

    this._buildPage();
    // qxapp.auth.core.BaseAuthPage.addPageToRoot(this);
  },

  destruct: function() {
    console.debug("Destroying ", Object.getPrototypeOf(this).classname);
  },

  members: {
    // override this method in subclass
    _buildPage: function() {},

    /**
     * Creates and adds an underlined title at the header
     */
    _addTitleHeader: function(txt) {
      var lbl = new qx.ui.basic.Label(txt).set({
        font: "headline",
        alignX: "center"
      });
      this.add(lbl, {
        flex:1
      });
    }
  }
});
