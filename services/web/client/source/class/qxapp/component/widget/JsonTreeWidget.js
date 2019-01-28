/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("qxapp.component.widget.JsonTreeWidget", {
  extend: qx.ui.core.Widget,

  construct: function(data, elemId) {
    this.base();

    this.addListenerOnce("appear", () => {
      let elem = this.getContentElement().getDomElement();
      qx.bom.element.Attribute.set(elem, "id", elemId);
      let jsonTreeViewer = qxapp.wrappers.JsonTreeViewer.getInstance();
      if (jsonTreeViewer.getLibReady()) {
        jsonTreeViewer.print(data, elem);
      }
    });
  }
});
