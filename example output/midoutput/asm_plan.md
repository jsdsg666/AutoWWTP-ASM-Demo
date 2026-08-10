# ASM Plan: Facultative Tank with COD, Nitrogen, and Phosphorus Removal

## User Input

Data are located at input/data31.xlsx. Build an ASM model to simulate a facultative tank, including COD degradation, complete nitrogen removal, and enhanced biological phosphorus removal. The boundary to consider is low aeration (oxygen transfer volumetric coefficient is 2 /h, and saturated dissolved oxygen concentration is 8.0 mg/L). Calibrate ammonia nitrogen, nitrate nitrogen, and orthophosphate. Please keep intermediate files and analyze the modeling process and results

## Process Identification Summary

This task models a single facultative CSTR for simultaneous COD degradation, complete nitrogen removal, and EBPR under low aeration. The dataset spans 21 ASM components and supports full nitrogen, phosphorus, and N2O pathways. Calibration targets ammonium, nitrate, and orthophosphate, requiring the IntegratedNPR modelcomplex with ParetoMOEA calibration. Only the low-aeration boundary is active.

## 1. Define Model Boundaries

The selected modelcomplex is IntegratedNPR because the task explicitly requires complete nitrogen removal, enhanced biological phosphorus removal, and the facultative regime implies full nitrogen-pathway intermediates including N2O. This is the only model option that simultaneously supports complete nitrogen transformations, complete phosphorus transformations, and N2O intermediates. The base representation is a single reaction-only CSTR with no hidden baseline boundaries; any oxygen transfer or other source/sink effects are represented exclusively through the Step 6 boundary menu and are injected into the right-hand side of the mass balances via the boundaries argument passed to run_pipeline in script/asmlibrary.py.

## 2. Define State Components

The IntegratedNPR modelcomplex enables all 21 ASM state components: soluble species S_sub_S, S_sub_I, S_sub_NH_sub_4, S_sub_NO_sub_2, S_sub_NO_sub_3, S_sub_NH_sub_2OH, S_sub_N_sub_2, S_sub_N_sub_2O, S_sub_NO, S_sub_ALK, S_sub_O_sub_2, and S_sub_PO_sub_4, plus particulate species X_sub_S, X_sub_I, X_sub_H, X_sub_AOB, X_sub_NOB, X_sub_STO, X_sub_PAO, X_sub_PHA, and X_sub_PP. All component names use the asmlibrary.py subscript convention with _sub_X syntax, and the state vector is ordered exactly as listed above for consistent stoichiometric slicing.

## 3. Determine Biochemical Reactions

The IntegratedNPR framework activates 41 biochemical reactions grouped as hydrolysis of X_sub_S to S_sub_S; heterotrophic storage of S_sub_S into X_sub_STO and aerobic/anoxic growth and endogenous decay of X_sub_H; three-step ammonia oxidation by X_sub_AOB through hydroxylamine to nitrite with associated N2O and NO emissions and AOB decay; nitrite oxidation by X_sub_NOB to nitrate and NOB decay; complete heterotrophic denitrification from nitrate through nitrite, NO, and N2O to N2; PAO anaerobic phosphate release linked to X_sub_PHA storage; PAO aerobic and anoxic growth with X_sub_PP accumulation; and PAO decay.

## 4. Build the Stoichiometric Matrix

The stoichiometric matrix for this configuration has 41 active reactions and 21 active components and is obtained by slicing the full asmlibrary.STOICHIOMETRY array to the rows and columns corresponding to the IntegratedNPR reaction set and the 21-component state vector. The sign and magnitude of each entry encode the yield of reactants and products per unit process rate, including the conserved COD, nitrogen, and phosphorus fractions required for heterotrophic, autotrophic, and PAO processes. The modeling_agent will construct this matrix directly from asmlibrary.py without manual transcription of individual stoichiometric coefficients.

## 5. Build Kinetic Rate Equations

Each reaction rate combines Monod saturation, product inhibition, dissolved-oxygen switching, and electron-acceptor preference functions to capture the facultative low-DO behavior. The complete parameter dictionary and symbolic rate-equation definitions reside in asmlibrary.PARAMS and asmlibrary.RATE_EQUATIONS, respectively, and are reused without modification. Because the full parameter set is large, only the subset identified in Step 7 will be adjusted during calibration; all other parameters remain fixed at their asmlibrary default values to avoid overparameterization while still reproducing the observed ammonium, nitrate, and orthophosphate dynamics.

## 6. Build Mass-Balance Equations

For every component i, the mass balance reads dC_i/dt = sum_j nu_ij rho_j + boundary_terms_i(t, state, env), where the summation runs over the 41 IntegratedNPR reaction rates and boundary_terms_i contains only the explicitly declared source/sink contributions. The task is a single-tank scenario, so no hydraulic, recycle, or dosing fluxes are added. The only user-specified boundary is low aeration, modeled as K_L_a multiplied by the dissolved-oxygen deficit and applied solely to S_sub_O_sub_2.

- Aeration boundary: K_L_a=2 /h, S_O_sat=8.0 mg/L (only S_sub_O_sub_2)

## 7. Run Sensitivity Analysis with Data

Using xlsx_path=input/data31.xlsx, perform a one-at-a-time sensitivity analysis by perturbing each parameter in asmlibrary.PARAMS by plus and minus sens_delta=0.10 and simulating the IntegratedNPR mass balances through run_pipeline. Compute normalized sensitivity coefficients for the calibration targets S_sub_NH_sub_4, S_sub_NO_sub_3, and S_sub_PO_sub_4, aggregate the absolute effects across all three targets, and rank the parameters. The top senstopk=8 parameters are selected as the calibration subset and written to midoutput/sensitivity.json, preserving this intermediate file as requested for later analysis of the modeling process.

## 8. Run Parameter Calibration

Run calibration with calibmode=ParetoMOEA because three targets are specified without explicit weight preference, using sens_targets={S_sub_NH_sub_4: 1.0, S_sub_NO_sub_3: 1.0, S_sub_PO_sub_4: 1.0}. The NSGA-II optimizer evolves the eight sensitivity-selected parameters for maxiter=150 generations, minimizing the normalized root-mean-square errors for ammonium, nitrate, and orthophosphate simultaneously and returning a Pareto front of trade-off solutions. The calibration history, final parameter sets, and objective values are saved to midoutput/calibration.json as an intermediate artifact.

## 9. Interpret Calibration Results

Interpret the Pareto front by reporting per-target NRMSE values: values at or below 0.30 indicate acceptable predictive performance, values between 0.30 and 0.60 are high but may still be usable for process understanding, and values above 0.60 indicate clearly high uncertainty. Examine the sensitivity ranking, the evolution of objectives, and any systematic bias in ammonium, nitrate, or orthophosphate fits to diagnose whether additional boundary terms, different parameter bounds, or model structure adjustments are warranted. The final deliverables are output/asm_report.md and output/asm_report.pdf, which summarize the calibration results and modeling-process analysis.