/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * The loading page
 */
qx.Class.define("osparc.ui.message.Loading", {
  extend: qx.ui.core.Widget,

  /**
   * Constructor for the Loading widget.
   *
   * @param {String} header Header that goes next to the spinning wheel.
   * @param {Array} messages Texts that will displayed as bullet points under the header.
   */
  construct: function(header, messages) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox());

    this.__buildLayout(header, messages);
  },

  members: {
    __buildLayout: function(header, messages) {
      const image = new osparc.ui.basic.OSparcLogo().set({
        width: 200,
        height: 120
      });

      const atom = new qx.ui.basic.Atom(header).set({
        icon: "@FontAwesome5Solid/circle-notch/32",
        font: "nav-bar-label",
        alignX: "center",
        gap: 10
      });
      atom.getChildControl("icon").getContentElement().addClass("rotate");

      const loadingWidget = new qx.ui.container.Composite(new qx.ui.layout.VBox().set({
        alignY: "middle"
      }));
      loadingWidget.add(new qx.ui.core.Widget(), {
        flex: 1
      });
      loadingWidget.add(image);
      loadingWidget.add(atom);
      loadingWidget.add(new qx.ui.core.Widget(), {
        flex: 1
      });

      this._add(new qx.ui.core.Widget(), {
        flex: 1
      });
      this._add(loadingWidget);
      this._add(new qx.ui.core.Widget(), {
        flex: 1
      });
    }
  }
});
