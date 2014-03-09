#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# networkx graph drawing script using Qt for graphics and udpsocket for drawing signal
# created by benjaminh on Tue Feb 25 2014
# 
# Based on a reference gexf graph file, this script waits for UDP socket packet
# to draw the node and its neighbours
# 1/ Once the file is executed, a blank window is displayed
# 2/ The program waits for an UDP signal. UDPReceiver is executed in separate thread
# 3/ When a packet is received, UDP thread emits a signal with selected node as parameter
# 4/ Main GUI thread draws the received node and its neighbours in a qgraphicsscene
#
#

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtNetwork import *

import os,sys, time
import socket # For UDP protocol

import networkx as nx # Module for drawing graphs
import numpy as np

# UDPReceiver working in background
class UdpReceiver(QObject):
	def __init__(self, parent = None):
		QObject.__init__(self,parent)
		self.port = 6005
		self.initialize()

	def initialize(self):
		self.s = QUdpSocket()
		self.s.bind(QHostAddress('127.0.0.1'),self.port) # Set the IP address to listen : 127.0.0.1 for localhost
		self.s.readyRead.connect(self.receive) # Connect the readyRead function to custom receive function
		self.old_node = '0'

	# Function receive waits for UDP datagrams and emits signal for main GUI thread
	def receive(self):
		while(self.s.hasPendingDatagrams()):
			datagram = QByteArray()
			size = self.s.pendingDatagramSize()
			data,addr,port = self.s.readDatagram(size)
			oldnode = self.old_node
			self.old_node = data.strip()
			self.emit(SIGNAL("draw(PyQt_PyObject,PyQt_PyObject)"),data.strip(),oldnode) # Send received datagram as Qt signal parameter

	def __del__(self):
		print "DESTRUCTOR"
		self.s.close()

# Node class herited from Qt QGraphicsItem class
class NodeItem(QGraphicsItem):
	def __init__(self, node, nodelabel, pos, radius=15, **args):
		QGraphicsItem.__init__(self, **args)
		self.pos = pos # Networkx list of graph items positions
		# Node creation
		self.node = node
		self.radius = radius
		x, y = pos[node]
		self.setPos(QPointF(x, y))
		self.nodelabel = nodelabel

		self.setFlag(QGraphicsItem.ItemIsMovable)
		self.setFlag(QGraphicsItem.ItemIsSelectable)
		self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)

	def update(self, *__args):
		self.setPos(*pos[self.node])

	def boundingRect(self):
		if self.isSelected():
			return QRectF(-2*self.radius, -2*self.radius, 4*self.radius, 4*self.radius)
		else:
			return QRectF(-self.radius, -self.radius, 2*self.radius, 2*self.radius)

	def paint(self, painter, style, widget=None):
		assert isinstance(painter, QPainter)

		qfont = QFont()
		# Node's color when selected
		if self.isSelected():
			brush = QBrush(Qt.yellow)
			qfont.setPointSize(16)
		else:
			brush = QBrush(Qt.white)
			qfont.setPointSize(6)

		color = QColor(0,0,0,50)
		pen = QPen(color)

		circle_path = QPainterPath()
		circle_path.addEllipse(self.boundingRect())
		painter.fillPath(circle_path, brush)
		painter.strokePath(circle_path, pen)

		# Position for node text
		text_path = QPainterPath()
		text_path.addText(0, 0, qfont, self.nodelabel)
		box = text_path.boundingRect()
		text_path.translate(-box.center())

		painter.fillPath(text_path, QBrush(Qt.black))

# Edge class herited from QGraphicsItem Qt4 class
class EdgeItem(QGraphicsItem):
	def __init__(self, source, target, pos, **args):
		QGraphicsItem.__init__(self, **args)
		self.source = source
		self.target = target
		self.pos = pos

	def boundingRect(self):
		x0, y0 = self.pos[self.source]
		x1, y1 = self.pos[self.target]
		return QRectF(min(x0, x1), min(y0, y1), abs(x1-x0), abs(y1-y0))

	def paint(self, painter, style, widget=None):
		assert(isinstance(painter, QPainter))
		x0, y0 = self.pos[self.source]
		x1, y1 = self.pos[self.target]
		color = QColor(0,0,0,50)
		pen = QPen(color)
		painter.setPen(pen)
		painter.drawLine(x0, y0, x1, y1)

class MyWindow(QMainWindow):
	def __init__(self,graph,position,parent = None):
		QMainWindow.__init__(self,parent)

		self.setFixedSize(1200,800) # To fit screen size. Didn't manage to resize the window automatically
		self.view = QGraphicsView(self)
		self.scene = QGraphicsScene()
		view = QGraphicsView(self.scene)
		self.view.setFixedSize(1200,800)

		self.pos = position
		self.g = graph
		graphic = self.g

		# Populate empty networkx graph with selected node and neighbors
		for edge in self.g.edges():
			self.scene.addItem(EdgeItem(edge[0], edge[1], self.pos))
		for node in self.g.nodes():
			self.scene.addItem(NodeItem(node,self.g.node[node]['label'],self.pos))

	def emitSignal(self):
		self.emit(SIGNAL("start_listening()"))
		self.show()

	# Function called by the UDP working thread when datagram is received
	def drawGraph(self,item,oldnode):
		if (oldnode != '0'):
			# Unselect old node and neighbors
			for oldneighbor in self.g.neighbors(oldnode):
				x, y = self.pos[oldneighbor]
				self.scene.itemAt(x,y).setSelected(False)
			xold,yold = self.pos[oldnode]
			self.scene.itemAt(xold,yold).setSelected(False)

		# Retrieve list of selected node's neighbors
		liste = self.g.neighbors(item)

		# SetSelected each of the neighbor in Qt Window
		for neighbor in liste:
			x, y = self.pos[neighbor]
			self.scene.itemAt(x,y).setSelected(True)
		x0,y0 = self.pos[item]
		self.scene.itemAt(x0,y0).setSelected(True)
		self.view.setScene(self.scene)

## Utility function
def eucl_dist(a,b):
    """
Euclidean distance
"""
    Di = [(a[i]-b[i])**2 for i in xrange(len(a))]
    return np.sqrt(np.sum(Di))

## Now the layout function
## https://github.com/tpoisot/nxfa2 with scale parameter added
def forceatlas2_layout(G, scale=1.0, iterations = 10, linlog = False, pos = None, nohubs = False, kr = 0.001, k = None, dim = 2):
    """
Options values are

g The graph to layout
iterations Number of iterations to do
linlog Whether to use linear or log repulsion
random_init Start with a random position
If false, start with FR
avoidoverlap Whether to avoid overlap of points
degreebased Degree based repulsion
"""
    # We add attributes to store the current and previous convergence speed
    for n in G:
        G.node[n]['prevcs'] = 0
        G.node[n]['currcs'] = 0
    # To numpy matrix
    # This comes from the spares FR layout in nx
    A=nx.to_scipy_sparse_matrix(G,dtype='f')
    nnodes,_=A.shape
    from scipy.sparse import spdiags,coo_matrix
    try:
        A=A.tolil()
    except:
        A=(coo_matrix(A)).tolil()
    if pos==None:
        pos=np.asarray(np.random.random((nnodes,dim)),dtype=A.dtype)
    else:
        pos=pos.astype(A.dtype)
    if k is None:
        k=np.sqrt(1.0/nnodes)
    # Iterations
    # the initial "temperature" is about .1 of domain area (=1x1)
    # this is the largest step allowed in the dynamics.
    t=0.1
    # simple cooling scheme.
    # linearly step down by dt on each iteration so last iteration is size dt.
    dt=t/float(iterations+1)
    displacement=np.zeros((dim,nnodes))
    for iteration in range(iterations):
        displacement*=0
        # loop over rows
        for i in range(A.shape[0]):
            # difference between this row's node position and all others
            delta=(pos[i]-pos).T
            # distance between points
            distance=np.sqrt((delta**2).sum(axis=0))
            # enforce minimum distance of 0.01
            distance=np.where(distance<0.01,0.01,distance)
            # the adjacency matrix row
            Ai=np.asarray(A.getrowview(i).toarray())
            # displacement "force"
            Dist = k*k/distance**2
            if nohubs:
                Dist = Dist/float(Ai.sum(axis=1)+1)
            if linlog:
                Dist = np.log(Dist+1)
            displacement[:,i]+=\
                (delta*(Dist-Ai*distance/k)).sum(axis=1)
        # update positions
        length=np.sqrt((displacement**2).sum(axis=0))
        length=np.where(length<0.01,0.1,length)
        pos+=(displacement*t/length).T
        # cool temperature
        t-=dt
    # Return the layout
    pos = _rescale_layout(pos,scale)
    return dict(zip(G,pos))

def _rescale_layout(pos,scale=1):
    # rescale to (0,pscale) in all axes

    # shift origin to (0,0)
    lim=0 # max coordinate for all axes
    for i in range(pos.shape[1]):
        pos[:,i]-=pos[:,i].min()
        lim=max(pos[:,i].max(),lim)
    # rescale to (0,scale) in all directions, preserves aspect
    for i in range(pos.shape[1]):
        pos[:,i]*=scale/lim
    return pos

def main():
	qApp = QApplication(sys.argv)

	# Read Gexf input graph file
	mygraph = nx.read_gexf("saint-sim.gexf")
	pos = forceatlas2_layout(mygraph,scale=1000)

	# Initialize UDP receiver and Qt window
	net = UdpReceiver()
	win = MyWindow(mygraph,pos)

	# Use signal/slots to communicate between qthreads
	t = QThread()
	net.moveToThread(t)
	QObject.connect(win,SIGNAL("start_listening()"),net.receive)
	QObject.connect(net,SIGNAL("draw(PyQt_PyObject,PyQt_PyObject)"),win.drawGraph)

	t.start()
	win.emitSignal() # Ready to listen UDP port
	
	sys.exit(qApp.exec_())

if __name__ == '__main__':
	main()
