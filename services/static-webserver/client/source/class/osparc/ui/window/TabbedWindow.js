/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.ui.window.TabbedWindow", {
  extend: osparc.ui.window.SingletonWindow,
  type: "abstract",

  construct: function(id, caption) {
    this.base(arguments, id, caption);

    this.setLayout(new qx.ui.layout.Grow());

    const defaultProps = this.self().DEFAULT_PROPS;
    this.set(defaultProps);
  },

  statics: {
    DEFAULT_PROPS: {
      modal: true,
      width: 900,
      height: 600,
      showMaximize: false,
      showMinimize: false,
      resizable: true,
      appearance: "service-window"
    }
  },

  members: {
    _setTabbedView: function(tabbedView) {
      this.add(tabbedView);
    }
  }
});
