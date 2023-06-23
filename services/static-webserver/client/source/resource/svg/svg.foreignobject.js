SVG.ForiegnObject = function() {
  this.constructor.call(this, SVG.create('foreignObject'))
  
  /* store type */
  this.type = 'foreignObject'
}

SVG.ForiegnObject.prototype = new SVG.Shape

SVG.extend(SVG.ForiegnObject, {
  appendChild: function (child, attrs) {
    var newChild = typeof(child)=='string' ? document.createElement(child) : child
    if (typeof(attrs)=='object'){
      for(a in attrs) newChild[a] = attrs[a]
    }
    this.node.appendChild(newChild)
    return this  
  },
  getChild: function (index) {
    return this.node.childNodes[index]
  }
})

SVG.extend(SVG.Container, {
  foreignObject: function(width, height) {
    return this.put(new SVG.ForiegnObject).size(width == null ? 100 : width, height == null ? 100 : height)
  }
})