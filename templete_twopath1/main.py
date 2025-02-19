#coding:utf8
from config import opt
import os
import torch as t
import models
from data.dataset import MriPet
from torch.utils.data import DataLoader
from torchnet import meter
from utils.visualize import Visualizer
from torch.optim import lr_scheduler as LRS
from tqdm import tqdm


@t.no_grad()  # pytorch>=0.5
def test(**kwargs):
    opt._parse(kwargs)

    # configure model
    model = getattr(models, opt.model)().eval()
    if opt.load_model_path:
        model.load(opt.load_model_path, opt.use_gpu)
    model.to(opt.device)

    # data
    train_data = MriPet(opt.test_data_root, opt.test_data_root1, test=True)
    test_dataloader = DataLoader(train_data, batch_size=opt.batch_size, shuffle=False, num_workers=opt.num_workers)
    results = []
    correct = 0
    for ii,(data1,data2,path) in tqdm(enumerate(test_dataloader)):
        input1 = data1.to(opt.device)
        input2 = data2.to(opt.device)
        path1 = path.to(opt.device)
        score = model(input1,input2)
        probability = t.nn.functional.softmax(score,dim=1)[:, 0].detach().tolist()
        pred = score.max(1, keepdim=True)[1]  # get the index of the max log-probability
        correct += pred.eq(path1.view_as(pred)).sum().item()
        batch_results = [(path_.item(),probability_) for path_,probability_ in zip(path,probability) ]
        results += batch_results

    print('Test set   Accuracy: ({:.2f}%)\n'.format(100 * correct / len(train_data)))
    write_csv(results, opt.result_file)
    # return results

def write_csv(results,file_name):
    import csv
    with open(file_name, 'w') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'label'])
        writer.writerows(results)
    
def train(**kwargs):
    opt._parse(kwargs)

    # vis = Visualizer(opt.env,port = opt.vis_port)

    # step1: configure model
    model = getattr(models, opt.model)()

    if opt.load_model_path:
        model.load(opt.load_model_path)
    model.to(opt.device)
    if opt.model == 'AlexNetCom':
        t.backends.cudnn.enabled = False  # 因为batch normalize的原因需要加上这一句

    # step2: data
    train_data = MriPet(opt.train_data_root, opt.train_data_root1, train=True)
    val_data = MriPet(opt.train_data_root, opt.train_data_root1, train=False)
    train_dataloader = DataLoader(train_data, opt.batch_size,
                        shuffle=True, num_workers=opt.num_workers)
    val_dataloader = DataLoader(val_data, opt.batch_size,
                        shuffle=False, num_workers=opt.num_workers)
    
    # step3: criterion and optimizer
    criterion = t.nn.CrossEntropyLoss()
    lr = opt.lr
    optimizer = model.get_optimizer(lr, opt.weight_decay)
    lr_scheduler = LRS.ExponentialLR(optimizer, gamma=opt.lr_decay)

    # step4: meters
    loss_meter = meter.AverageValueMeter()
    confusion_matrix = meter.ConfusionMeter(4)
    previous_loss = 1e10

    # train
    for epoch in range(opt.max_epoch):

        loss_meter.reset()
        confusion_matrix.reset()

        for ii, (data1, data2, label) in tqdm(enumerate(train_dataloader)):

            # train model 
            input1 = data1.to(opt.device)
            input2 = data2.to(opt.device)
            target = label.to(opt.device)

            optimizer.zero_grad()
            score = model(input1, input2)
            loss = criterion(score, target)
            loss.backward()
            optimizer.step()

            # meters update and visualize
            loss_meter.add(loss.item())
            # detach 一下更安全保险
            confusion_matrix.add(score.detach(), target.detach()) 

            if (ii + 1) % opt.print_freq == 0:
                print('Train Epoch: {}\t Loss: {:.6f},  lr={:.5f}'.format(epoch, loss_meter.value()[0],
                                                                          optimizer.param_groups[0]['lr']))
                # vis.plot('loss', loss_meter.value()[0])

                # 进入debug模式
                if os.path.exists(opt.debug_file):
                    import ipdb
                    ipdb.set_trace()

        if epoch % 100 == 99:
            model.save(epoch=epoch, label=opt.label_name)

        # validate and visualize
        val_cm, val_accuracy = val(model, val_dataloader)
        # update learning rate by lr_scheduler
        lr_scheduler.step(epoch=epoch)

        print('Val set: Average loss: {:.4f}, Accuracy: ({:.2f}%)\n'.format(loss_meter.value()[0], val_accuracy))
        with open(opt.loss_file, 'a') as f:
            f.write(str(loss_meter.value()[0]) + '\n')
        with open(opt.acc_file, 'a') as f:
            f.write(str(val_accuracy) + '\n')

        # vis.plot('val_accuracy',val_accuracy)
        # vis.log("epoch:{epoch},lr:{lr},loss:{loss},train_cm:{train_cm},val_cm:{val_cm}".format(
        #             epoch = epoch,loss = loss_meter.value()[0],val_cm = str(val_cm.value()),train_cm=str(confusion_matrix.value()),lr=lr))
        
        # update learning rate by validation
        if loss_meter.value()[0] > previous_loss:
            lr = lr * opt.lr_decay
            # 第二种降低学习率的方法:不会有moment等信息的丢失
            for param_group in optimizer.param_groups:
                param_group['lr'] = lr
        previous_loss = loss_meter.value()[0]

@t.no_grad()
def val(model, dataloader):
    """
    计算模型在验证集上的准确率等信息
    """
    model.eval()
    confusion_matrix = meter.ConfusionMeter(4)
    for ii, (val_input1, val_input2, label) in enumerate(dataloader):
        val_input1 = val_input1.to(opt.device)
        val_input2 = val_input2.to(opt.device)
        score = model(val_input1, val_input2)
        confusion_matrix.add(score.detach().squeeze(), label.type(t.LongTensor))

    model.train()
    cm_value = confusion_matrix.value()
    cm_value1 = 0
    for i in range(cm_value.shape[0]):
        cm_value1 = cm_value1 + cm_value[i][i]
    accuracy = 100. * cm_value1 / (cm_value.sum())
    return confusion_matrix, accuracy

def help():
    """
    打印帮助的信息： python file.py help
    """
    
    print("""
    usage : python file.py <function> [--args=value]
    <function> := train | test | help
    example: 
            python {0} train --env='env0701' --lr=0.01
            python {0} test --dataset='path/to/dataset/root/'
            python {0} help
    avaiable args:""".format(__file__))

    from inspect import getsource
    source = (getsource(opt.__class__))
    print(source)

if __name__=='__main__':
    import fire
    fire.Fire()
