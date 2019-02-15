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

/**
 * Widget containing a JsonTreeViewer dom element
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let jsonTreeWidget = new qxapp.component.widget.JsonTreeWidget(data, "elemId");
 *   this.getRoot().add(jsonTreeWidget);
 * </pre>
 */

qx.Class.define("qxapp.component.widget.JsonTreeWidget", {
  extend: qx.ui.core.Widget,

  /**
    * @param data {Object} Json object to be displayed by JsonTreeViewer
    * @param elemId {String} Element id to set it as dom attribute
  */
  construct: function(data, elemId) {
    this.base();

    this.addListenerOnce("appear", () => {
      let elem = this.getContentElement().getDomElement();
      qx.bom.element.Attribute.set(elem, "id", elemId);
      let jsonTreeViewer = qxapp.wrapper.JsonTreeViewer.getInstance();
      if (jsonTreeViewer.getLibReady()) {
        jsonTreeViewer.print(data, elem);
      }
    });
  }
});
