from random import shuffle
import numpy as np

import torch
import torch.nn as nn
from torch.autograd import Variable


class Solver(object):
	'''
	TO DO: have a measure for performance over time such as NSS or MSE to observe behavior on validation data
	'''

	default_adam_args = {"lr": 1e-4,
		 "betas": (0.9, 0.999),
		 "eps": 1e-8,
		 "weight_decay": 0.0}

	def __init__(self, optim=torch.optim.Adam, optim_args={}):
		optim_args_merged = self.default_adam_args.copy()
		optim_args_merged.update(optim_args)
		self.optim_args = optim_args_merged
		self.optim = optim
				
		self.oneDivSqrtTwoPI = 1.0 / math.sqrt(2.0*math.pi) # normalisation factor for gaussian.
		self.oneDivTwoPI = 1.0 / (2.0*math.pi)
        
        self._reset_histories()

	def _reset_histories(self):
		"""
		Resets train and val histories for the accuracy and the loss.
		"""
		self.train_loss_history = []
		self.train_acc_history = []
		self.val_acc_history = []
		self.val_loss_history = []
        
		
	def _gaussian_distribution2d(self, out_mu_x, out_mu_y, out_sigma, out_corr, fix_data):
    
		nFrames, nFixs,_ = fix_data.size()
		KMIX = out_mu_x.size(1)
		# combine x and y mean values
		out_mu_xy = torch.cat((out_mu_x.unsqueeze(2), out_mu_y.unsqueeze(2)),2)
		# braodcast subtraction with mean and normalization to sigma
		fix_data = fix_data.expand(KMIX, *fix_data.size())
		out_mu_xy = out_mu_xy.expand(nFixs, *out_mu_xy.size())
		out_mu_xy = out_mu_xy.contiguous().view(fix_data.size())
		out_sigma = out_sigma.expand(nFixs, *out_sigma.size())
		out_sigma = out_sigma.contiguous().view(fix_data.size()[:-1])
		out_corr = out_corr.expand(nFixs, *out_corr.size())
		out_corr = out_corr.contiguous().view(fix_data.size()[:-1])
		
		result = (fix_data - out_mu_xy) 
		result = result[:,:,:,0]**2 + result[:,:,:,1]**2 - 2*out_corr*result.prod(3)
		result *= torch.reciprocal(out_sigma**2)
		result *= -0.5 * torch.reciprocal(1-out_corr**2)
		result = self.oneDivTwoPI * torch.reciprocal(torch.sqrt(1-out_corr**2)) * torch.exp(result)

		return result
	
	
	def mdn_loss_function(self, out_pi, out_mu_x, out_mu_y, out_sigma, out_corr, fix_data):

			result = self._gaussian_distribution2d(out_mu_x, out_mu_y, out_sigma, out_corr, fix_data) * out_pi
			result = torch.sum(result, dim=0)
			result = - torch.log(result)

			return torch.mean(result)



	def train(self, model, train_loader, val_loader, num_epochs=10, log_nth=0):
        """
        Train a given model with the provided data.

        Inputs:
        - model: model object initialized from a torch.nn.Module
        - train_loader: train data in torch.utils.data.DataLoader
        - val_loader: val data in torch.utils.data.DataLoader
        - num_epochs: total number of training epochs
        - log_nth: log training accuracy and loss every nth iteration
        """
		optim = self.optim(model.parameters(), **self.optim_args)
		self._reset_histories()
		iter_per_epoch = len(train_loader)

		if torch.cuda.is_available():
		    model.cuda()

		print('START TRAIN.')

		nIterations = num_epochs*iter_per_epoch


		for i in range(num_epochs):
		    for j, (inputs, labels) in enumerate(train_loader, 0):

			it = i*iter_per_epoch + j

			inputs = Variable(inputs)
			labels = Variable(labels)
			(out_pi, out_mu_x, out_mu_y, out_sigma, out_corr) = model(x_train)
			loss = self.mdn_loss_function(out_pi, out_mu_x, out_mu_y, out_sigma, out_corr, y_train)
			if it%log_nth==0:
			    print('[Iteration %i/%i] TRAIN loss: %f' % (it,nIterations,loss))
			    self.train_loss_history.append(loss)

			optim.zero_grad()
			loss.backward()
			optim.step()

		    #train_acc = (np.squeeze(np.array(max_index)) == np.squeeze(np.array(labels))).mean()
		    #self.train_acc_history.append(train_acc)

		    inputs_val = Variable(torch.from_numpy(val_loader.dataset.X))
		    labels_val = Variable(torch.from_numpy(val_loader.dataset.y))
		    (out_pi, out_mu_x, out_mu_y, out_sigma, out_corr) = model.forward(inputs_val)
		    loss_val = self.mdn_loss_function(out_pi, out_mu_x, out_mu_y, out_sigma, out_corr, y_train)

		    #val_acc = (np.squeeze(np.array(max_index_val)) == np.squeeze(np.array(labels_val))).mean()
		    #self.val_acc_history.append(val_acc)
		    #print('[Epoch %i/%i] TRAIN acc/loss: %f/%f' % (i,num_epochs,train_acc, loss))
		    #print('[Epoch %i/%i] VAL acc/loss: %f/%f' % (i,num_epochs,val_acc, loss_val))
							print('[Epoch %i/%i] TRAIN loss: /%f' % (i,num_epochs,loss))
		    print('[Epoch %i/%i] VAL loss: %f' % (i,num_epochs,loss_val))


		print('FINISH.')
        
        
        
if __name__ == '__main__':

	# ==== Testing MDN1D (forward and backward pass) ====
	FNUM = 10  # number of frames!
	inp_data = np.float32(np.random.rand(FNUM, 256))
	inp_data = Variable(torch.from_numpy(inp_data))
	fix_data = np.float32(np.random.rand(FNUM, 10, 2)) # FNUM frames, 10 fixation points
	fix_data = Variable(torch.from_numpy(fix_data), requires_grad=False)

	H, KMIX = 128, 10
	model = MDN1D(hidden_size=H, num_mixtures=KMIX)

	solver_obj = Solver()
	solver_obj.train(inp_data, fix_data)


	# ===== Testing MDN2D (forward and backward pass) =====
	FNUM = 10  # number of frames!
	inp_data = np.float32(np.random.rand(FNUM,3,32,32))
	inp_data = Variable(torch.from_numpy(inp_data))
	fix_data = np.float32(np.random.rand(FNUM, 10, 2)) # FNUM frames, 10 fixation points
	fix_data = Variable(torch.from_numpy(fix_data), requires_grad=False)

	# defining the network
	h_in, w_in, H, KMIX = inp_data.size(-2), inp_data.size(-1), 256, 10 
	model = MDN2D(in_height=h_in, in_width=w_in, hidden_size=H, num_mixtures=KMIX)

	solver_obj = Solver()
solver_obj.train(inp_data, fix_data)
