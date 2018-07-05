/*

  TODO: add alternative logins
*/

/**
 * This is a basic Auth-Page with common functionality
 *
 *  - Fixed-size widget with header (title/logo), body and footer (buttons)
 *  - Positioned at the upper center of the root document's window
 */
qx.Class.define("qxapp.auth.BaseAuthPage", {
  extend: qx.ui.container.Composite,
  include: [
    qxapp.auth.MAuth
  ],
  type: "abstract",

  statics: {

    addPageToRoot: function(page) {
      // TODO: should be automatically reposition of document size changed!?
      let top = parseInt((qx.bom.Document.getHeight() - page.getHeight()) / 4, 10);
      let left = parseInt((qx.bom.Document.getWidth() - page.getWidth()) / 2, 10);
      let app = qx.core.Init.getApplication();
      app.getRoot().add(page, {
        top: top,
        left: left
      });
    }
  },


  construct: function() {
    this.base(arguments);

    // Setup children's layout and the auth page widget dimensions
    const spacing = 10;
    this.setLayout(new qx.ui.layout.VBox(spacing));
    this.set({
      width: 300,
      height: 250
    });

    // layout values
    this._widthBtn = parseInt((this.getWidth() - 30) / 2, 10);
    this._marginFooter = 3*spacing;

    this._buildPage();
    qxapp.auth.BaseAuthPage.addPageToRoot(this);
  },

  destruct: function() {
    // TODO: check order of destruction
    console.debug("destroying AuthBasePage");
  },

  members: {
    _widthBtn: 20,
    _gapTitle: 20,
    _gapBtns: 20,
    // override
    _buildPage: function() {
      console.error("This should be overriden");
    },

    /**
     * Creates and adds an underlined title at the header
     */
    _addTitleHeader: function(txt) {
      var font = new qx.bom.Font(24, ["Arial"]);
      font.setBold(true);

      var lbl = new qx.ui.basic.Label("<center><b style='color: #FFFFFF'>" + txt + "</b></center>");
      lbl.set({
        font: font,
        rich: true,
        width: this.getWidth()
      });
      this.add(lbl);


      const spacing = this.getLayout().getSpacing();
      var line = new qx.ui.core.Widget();
      line.set({
        height: 1,
        backgroundColor: "white",
        marginBottom: 3*spacing
      });
      this.add(line);
    }
  }
});
