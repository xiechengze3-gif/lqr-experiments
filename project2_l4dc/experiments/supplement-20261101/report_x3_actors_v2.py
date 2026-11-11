"""Primary X3 endpoint report plus fixed-order envelope and Review04:35 mechanism."""
from actor_report import report
from npg_order_report import extend
from npg_last_stage_report import run

if __name__=='__main__':
    report('X3')
    extend()
    run()
