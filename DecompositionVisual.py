import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib import colors

def SquareVisualization():
    dimension = 15
    x = np.zeros((dimension**2,dimension**2))

    TerminalLocations = [[0,6],[6,0],[6,6]]
    Rewards = [-1,1,2]

    skips = []
    w_i = []
    w = np.zeros((dimension**2))
    for i,loc in enumerate(TerminalLocations):
        skips.append(loc[0]+dimension*loc[1])
        w[loc[0]+dimension*loc[1]] = Rewards[i]

        tmp = np.zeros((dimension**2))
        tmp[loc[0]+dimension*loc[1]] = Rewards[i]
        w_i.append(tmp)

    for i in range(dimension**2):
        if i in skips:
            continue
        sum = 0
        if i % dimension != dimension-1:
            x[i,i+1] = 0.25
            sum += 0.25
        if i % dimension != 0:
            x[i,i-1] = 0.25
            sum += 0.25
        if i >= dimension:
            x[i,i-dimension] = 0.25
            sum += 0.25
        if i <= dimension**2-dimension-1:
            x[i,i+dimension] = 0.25
            sum += 0.25
        x[i,i]= 1.0-sum

    I = np.identity(dimension**2)
    psi = np.linalg.inv(I-x)


    images = []
    fig,axs = plt.subplots(2, 2)

    value = np.reshape(np.matmul(psi,w),(dimension,dimension))
    images.append(axs[0,0].imshow(value))
    axs[0,0].set_title("Global Value Estimate")
    axs[0,0].label_outer()

    for i,w_ in enumerate(w_i):
        value_i = np.reshape(np.matmul(psi,w_),(dimension,dimension))
        images.append(axs[(i+1)//2,(i+1)%2].imshow(value_i))
        axs[(i+1)//2,(i+1)%2].set_title("Value Estimate from " + str(i))
        axs[(i+1)//2,(i+1)%2].label_outer()

    vmin = min(image.get_array().min() for image in images)
    vmax = max(image.get_array().max() for image in images)
    norm = colors.Normalize(vmin=vmin, vmax=vmax)
    for im in images:
        im.set_norm(norm)
    fig.colorbar(images[0], ax=axs, orientation='horizontal', fraction=.1)
    plt.show()

def ObstacleVisualization(location=[7,7],reward=[1.0],plotting=True):
    grid = np.array([   [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,1,1,1,1,0,1,1,1,1,1,1,1,1,0,1,1,1,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
                        ])
    TerminalLocations = location
    Rewards = reward
    gamma = 0.99

    obstacles = np.sum(grid)
    size = grid.shape[0]*grid.shape[1]
    states = size-obstacles

    x = np.zeros((states,states))
    # states = {}
    # states_ = []
    states_ = {}
    count = 0
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            if grid[i,j] == 0:
                states_[count] = [i,j]
                # states_.append([count, [i,j]])
                count+=1
    skips = []
    w_i = []
    w = np.zeros((states))
    for i,loc in enumerate(TerminalLocations):
        for j in range(len(states_)):
            if states_[j] == loc:
                skips.append(j)
                w[j] = Rewards[i]

                tmp = np.zeros((states))
                tmp[j] = Rewards[i]
                w_i.append(tmp)

    for i in range(len(states_)):
        [locx,locy] = states_[i]
        sum = 0
        if i in skips:
            continue
        for j in range(len(states_)):
            if states_[j] == [locx+1,locy]:
                x[i,j] = 0.25
                sum += 0.25
            if states_[j] == [locx-1,locy]:
                x[i,j] = 0.25
                sum += 0.25
            if states_[j] == [locx,locy+1]:
                x[i,j] = 0.25
                sum += 0.25
            if states_[j] == [locx,locy-1]:
                x[i,j] = 0.25
                sum += 0.25
        x[i,i]= 1.0-sum
    I = np.identity(states)
    psi = np.linalg.inv(I-gamma*x)

    valueGrid = np.zeros_like(grid,dtype=float)

    value = np.matmul(psi,w)
    for j in range(len(states_)):
        loc = states_[j]
        valueGrid[loc[0],loc[1]] = value[j]

    if plotting:
        images = []
        fig,axs = plt.subplots(1,1)
        images.append(axs.imshow(valueGrid))
        axs.set_title("True Value: Gamma=0.99")
        axs.label_outer()

        # for i,w_ in enumerate(w_i):
        #     # value_i = np.reshape(np.matmul(psi,w_),(dimension,dimension))
        #     images.append(axs[(i+1)//2,(i+1)%2].imshow(valueGrid))
        #     axs[(i+1)//2,(i+1)%2].set_title("Value Estimate from " + str(i))
        #     axs[(i+1)//2,(i+1)%2].label_outer()
        #
        # vmin = min(image.get_array().min() for image in images)
        # vmax = max(image.get_array().max() for image in images)
        # norm = colors.Normalize(vmin=vmin, vmax=vmax)
        # for im in images:
        #     im.set_norm(norm)
        fig.colorbar(images[0], ax=axs, orientation='vertical', fraction=.1)
        plt.show()
    return valueGrid

def ObstacleVisualization_v2(plotting=True, probs=[0.25,0.25,0.25,0.25]):
    grid = np.array([   [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,1,1,1,1,1,0,1,1,1,1,1,1,1,0,1,1,1,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1],
                        [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
                        ])
    TerminalLocations = [[9,14]]
    Rewards = [1]
    gamma = 0.99

    obstacles = np.sum(grid)
    size = grid.shape[0]*grid.shape[1]
    states = size-obstacles

    x = np.zeros((states,states))
    # states = {}
    # states_ = []
    states_ = {}
    count = 0
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            if grid[i,j] == 0:
                states_[count] = [i,j]
                # states_.append([count, [i,j]])
                count+=1
    skips = []
    w_i = []
    w = np.zeros((states))
    for i,loc in enumerate(TerminalLocations):
        for j in range(len(states_)):
            if states_[j] == loc:
                skips.append(j)
                w[j] = Rewards[i]

                tmp = np.zeros((states))
                tmp[j] = Rewards[i]
                w_i.append(tmp)
    entropy=[]
    for i in range(len(states_)):
        [locx,locy] = states_[i]
        sum = 0
        if i in skips:
            continue
        if probs == "Random":
            probabilities=np.random.dirichlet(np.ones(4)*1,size=1)[0]
        else:
            probabilities=probs
        entropy.append(-np.sum(probabilities * np.log2(probabilities)))
        print(probabilities)
        for j in range(len(states_)):
            if states_[j] == [locx+1,locy]:
                x[i,j] = probabilities[0]
                sum += probabilities[0]
            if states_[j] == [locx-1,locy]:
                x[i,j] = probabilities[1]
                sum += probabilities[1]
            if states_[j] == [locx,locy+1]:
                x[i,j] = probabilities[2]
                sum += probabilities[2]
            if states_[j] == [locx,locy-1]:
                x[i,j] = probabilities[3]
                sum += probabilities[3]
        x[i,i]= 1.0-sum
    print(np.average(entropy))
    I = np.identity(states)
    psi = np.linalg.inv(I-gamma*x)

    w_g,v_g = np.linalg.eig(psi)


    for i in range(5):
        valueGrid = np.zeros_like(grid,dtype=float)
        value=np.matmul(x,np.expand_dims(v_g[:,i],1))
        for j in range(len(states_)):
            loc = states_[j]
            valueGrid[loc[0],loc[1]] = np.real(value[j])

        if plotting:
            images = []
            fig,axs = plt.subplots(1,1)
            images.append(axs.imshow(valueGrid))
            axs.set_title("Value Function from EigenVector "+str(i))
            axs.label_outer()

            # for i,w_ in enumerate(w_i):
            #     images.append(axs[(i+1)//2,(i+1)%2].imshow(valueGrid))
            #     axs[(i+1)//2,(i+1)%2].set_title("Value Estimate from " + str(i))
            #     axs[(i+1)//2,(i+1)%2].label_outer()

            vmin = min(image.get_array().min() for image in images)
            vmax = max(image.get_array().max() for image in images)
            norm = colors.Normalize(vmin=vmin, vmax=vmax)
            for im in images:
                im.set_norm(norm)
            fig.colorbar(images[0], ax=axs, orientation='vertical', fraction=.1)
            # plt.show()
            plt.savefig("Option"+str(i)+".png")
            plt.close()
    return valueGrid

def DiffusionTime(dimension=30):

    x = np.zeros((dimension**2,dimension**2))


    for i in range(dimension**2):
        sum = 0
        if i % dimension != dimension-1:
            x[i,i+1] = 0.25
            sum += 0.25
        if i % dimension != 0:
            x[i,i-1] = 0.25
            sum += 0.25
        if i >= dimension:
            x[i,i-dimension] = 0.25
            sum += 0.25
        if i <= dimension**2-dimension-1:
            x[i,i+dimension] = 0.25
            sum += 0.25
        x[i,i]= 1.0-sum
    I = np.identity(dimension**2)
    psi = np.linalg.inv(I-0.98*x)

    occupancy = np.reshape(psi[465,:],(dimension,dimension))

    fig=plt.figure(figsize=(5.5, 5.5))
    fig.add_subplot(1,1,1)
    plt.title("State Occupancy")
    imgplot = plt.imshow(occupancy,)
    plt.show()
    plt.close()



if __name__ == "__main__":
    # ObstacleVisualization(location=[[9,14]])
    # ObstacleVisualization(location=[[7,7]])
    # ObstacleVisualization(location=[[7,7],[9,14]],reward=[4.0,2.04])

    # ObstacleVisualization_v2(probabilities=[0.25,0.25,0.25,0.25])
    # ObstacleVisualization_v2()
    # ObstacleVisualization_v2(probs="Random")

    DiffusionTime()
